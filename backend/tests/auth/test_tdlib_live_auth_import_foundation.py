from __future__ import annotations

import base64
from io import BytesIO
import json
import zipfile

from fastapi.testclient import TestClient

from app.db import Base
from app.config import Settings
from app.main import app
from app.models import AccountImportBatch, SensitiveAuditEvent, TelegramAuthSession
from app.scripts.tdlib_runtime_smoke import main as tdlib_runtime_smoke_main
from app.services.database import create_sqlite_test_session_factory
from app.services.import_validation import validate_import_source
from app.services.tdlib_paths import build_auth_session_tdlib_paths
from app.services.tdlib_runtime import detect_tdlib_runtime
from app.services.worker_plane import assert_queue_allowed, worker_diagnostics

from conftest import override_app_session


def test_tdlib_runtime_disabled_default_is_safe() -> None:
    status = detect_tdlib_runtime(
        Settings(tdlib_live_enabled=False, tdlib_shared_library_path=None)
    )

    assert status.live_enabled is False
    assert status.configured is False
    assert status.library_loadable is False
    assert "path" not in str(status.to_safe_dict()).lower()


def test_tdlib_runtime_smoke_json_default_is_safe(capsys) -> None:
    exit_code = tdlib_runtime_smoke_main(["--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PASS"
    assert payload["checks"]["runtime"] == "PASS"
    assert payload["checks"]["library"] == "SKIP"
    assert payload["checks"]["readonly_auth"] == "DISABLED"
    serialized = json.dumps(payload).lower()
    assert "tdlib/database" not in serialized
    assert "telegram_api_hash" not in serialized


def test_tdlib_runtime_smoke_readonly_auth_requires_explicit_flags(capsys) -> None:
    exit_code = tdlib_runtime_smoke_main(
        ["--readonly-auth-check", "--auth-session-id", "auth-1", "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"]["readonly_auth"] == "DISABLED"
    assert payload["readonly_auth_check"] == "disabled"


def test_worker_diagnostics_are_safe_and_queue_allowlist_rejects_unknown() -> None:
    diagnostics = worker_diagnostics(
        Settings(
            tdlib_database_root="C:/private/tdlib/database",
            tdlib_files_root="C:/private/tdlib/files",
            tdlib_shared_library_path="C:/private/libtdjson.dll",
        )
    )

    assert_queue_allowed("auth_jobs")
    try:
        assert_queue_allowed("unknown_jobs")
    except ValueError as exc:
        assert "unsupported worker queue" in str(exc)
    else:
        raise AssertionError("unknown queue was accepted")

    assert diagnostics["tdlib"]["auth_worker_ready"] is True
    assert diagnostics["tdlib"]["live_enabled"] is False
    assert diagnostics["redis"]["status"] in {"ok", "down"}
    assert {"depth", "failed", "started", "deferred", "oldest_job_age_seconds"}.issubset(
        diagnostics["redis"]["queues"][0]
    )
    serialized = str(diagnostics).lower()
    assert "private/tdlib" not in serialized
    assert "libtdjson.dll" not in serialized


def test_tdlib_paths_are_isolated_and_reject_traversal(tmp_path) -> None:
    config = Settings(tdlib_database_root=tmp_path / "db", tdlib_files_root=tmp_path / "files")
    paths = build_auth_session_tdlib_paths(
        workspace_id="workspace-1", auth_session_id="auth-1", config=config
    )

    assert paths.storage_key == "workspace-1/auth-sessions/auth-1"
    assert paths.database_path.is_relative_to((tmp_path / "db").resolve())
    assert paths.files_path.is_relative_to((tmp_path / "files").resolve())

    try:
        build_auth_session_tdlib_paths(
            workspace_id="workspace-1", auth_session_id="../escape", config=config
        )
    except ValueError as exc:
        assert "unsafe" in str(exc) or "relative" in str(exc)
    else:
        raise AssertionError("unsafe TDLib path segment was accepted")


def test_auth_session_start_is_explicit_audited_and_does_not_persist_code() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    override_app_session(session_factory)
    try:
        response = TestClient(app).post(
            "/api/accounts/auth-sessions", json={"phone_number": "+15550104444", "label": "main"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    payload = response.json()
    assert payload["phone_hint"] == "***4444"
    assert payload["last_error_code"] == "tdlib_live_disabled"
    assert "tdlib" in payload["last_error_message"].lower()

    with session_factory() as session:
        row = session.get(TelegramAuthSession, payload["id"])
        assert row is not None
        serialized = str(row.__dict__).lower()
        assert "15550104444" not in serialized
        assert "12345" not in serialized
        actions = {event.action for event in session.query(SensitiveAuditEvent).all()}
        assert "telegram.auth.started" in actions
        assert "telegram.auth.start" in actions
    engine.dispose()


def test_auth_code_submit_does_not_enqueue_secret_job(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    override_app_session(session_factory)
    client = TestClient(app)
    enqueued: list[tuple] = []

    def fake_enqueue(*args, **kwargs):
        enqueued.append((args, kwargs))
        return True

    monkeypatch.setattr("app.api.telegram_auth.enqueue_telegram_auth_action", fake_enqueue)
    try:
        created = client.post("/api/accounts/auth-sessions", json={"phone_number": "+15550104445"})
        submitted = client.post(
            f"/api/accounts/auth-sessions/{created.json()['id']}/code", json={"code": "12345"}
        )
    finally:
        app.dependency_overrides.clear()

    assert created.status_code == 201
    assert submitted.status_code == 200
    serialized_jobs = str(enqueued)
    assert "12345" not in serialized_jobs
    assert all(kwargs.get("secret_value") is None for _, kwargs in enqueued)
    engine.dispose()


def test_import_validation_rejects_zip_slip_and_reports_unsupported_session() -> None:
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../evil.txt", "x")

    rejected = validate_import_source(source_type="tdlib-directory", content=archive.getvalue())
    unsupported = validate_import_source(source_type="session-file", content=b"fake")

    assert rejected[0].status == "unsupported"
    assert rejected[0].validation_code == "archive_rejected"
    assert unsupported[0].validation_code == "unsupported_source_requires_manual_reauth"
    assert "manual reauthorization" in unsupported[0].validation_message.lower()


def test_import_validation_rejects_symlink_and_oversized_archive() -> None:
    symlink_archive = BytesIO()
    with zipfile.ZipFile(symlink_archive, "w") as zf:
        info = zipfile.ZipInfo("link")
        info.external_attr = 0o120777 << 16
        zf.writestr(info, "target")

    oversized_archive = BytesIO()
    with zipfile.ZipFile(oversized_archive, "w") as zf:
        zf.writestr("large.bin", b"x" * 8)

    symlink_result = validate_import_source(
        source_type="tdlib-directory", content=symlink_archive.getvalue()
    )
    oversized_result = validate_import_source(
        source_type="tdlib-directory",
        content=oversized_archive.getvalue(),
        config=Settings(account_import_max_uncompressed_bytes=4),
    )

    assert symlink_result[0].validation_code == "archive_rejected"
    assert "symlinks" in symlink_result[0].validation_message
    assert oversized_result[0].validation_code == "archive_rejected"
    assert "too large" in oversized_result[0].validation_message


def test_import_batch_preview_is_private_dry_run_and_secret_safe() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    override_app_session(session_factory)
    client = TestClient(app)
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("td.bin", "placeholder")

    try:
        created = client.post(
            "/api/account-import-batches",
            json={"source_type": "tdlib-directory", "label": "dry run", "dry_run": True},
        )
        validated = client.post(
            f"/api/account-import-batches/{created.json()['id']}/validate",
            json={"content_base64": base64.b64encode(archive.getvalue()).decode("ascii")},
        )
    finally:
        app.dependency_overrides.clear()

    assert created.status_code == 201
    assert validated.status_code == 200
    payload = validated.json()
    assert payload["dry_run"] is True
    assert payload["status"] == "preview_ready"
    assert payload["items"][0]["validation_code"] == "tdlib_structure_detected"
    serialized = str(payload).lower()
    assert "auth_key" not in serialized
    assert "password" not in serialized

    with session_factory() as session:
        batch = session.get(AccountImportBatch, payload["id"])
        assert batch is not None
        assert batch.object_key.startswith("imports/")
    engine.dispose()
