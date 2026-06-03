from __future__ import annotations

import base64
import io
from datetime import timedelta
from zipfile import ZipFile, ZipInfo

import pytest

from app.config import settings
from app.models import (
    DEFAULT_LOCAL_USER_ID,
    DEFAULT_LOCAL_WORKSPACE_ID,
    AccountOnboardingArtifact,
    AccountOnboardingBatch,
    AccountOnboardingEvent,
    AccountOnboardingItem,
    TelegramAuthSession,
    Workspace,
    utc_now,
)
from app.modules.account_onboarding import service as onboarding_service
from app.modules.account_onboarding import artifacts as onboarding_artifacts


@pytest.fixture(autouse=True)
def _account_onboarding_storage_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "storage_local_root", tmp_path / "storage")


def test_account_onboarding_phone_batch_validates_as_canonical_flow(app_client) -> None:
    create = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "onboarding-create-1",
            "source_type": "phone",
            "label": "June",
            "phone_items": [{"phone_number": "+1 (555) 010-2000", "label": "A"}],
        },
    )

    assert create.status_code == 201
    batch_id = create.json()["batch"]["id"]
    validate = app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/validate",
        json={"idempotency_key": "onboarding-validate-1"},
    )

    assert validate.status_code == 200
    body = validate.json()
    assert body["batch"]["source_type"] == "phone_bulk"
    assert body["batch"]["status"] == "preview_ready"
    assert body["items"][0]["status"] == "valid"
    assert body["items"][0]["phone_hint"] == "***2000"
    assert "phone_number" not in body["items"][0]


def test_account_onboarding_confirm_requires_consent(app_client) -> None:
    created = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "onboarding-create-2",
            "source_type": "json_metadata",
            "metadata_json": {"username": "demo"},
        },
    ).json()
    batch_id = created["batch"]["id"]
    app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/validate",
        json={"idempotency_key": "onboarding-validate-2"},
    )

    response = app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/confirm",
        json={
            "idempotency_key": "onboarding-confirm-2",
            "confirmation": "ADD_ACCOUNTS",
            "consent_accepted": False,
            "consent_version": "v1",
        },
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "ONBOARDING_CONSENT_REQUIRED"
    assert response.json()["details"]["request_id"] == response.json()["request_id"]
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


def test_account_onboarding_artifact_rejects_zip_slip_and_hides_object_key(app_client) -> None:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("../tdlib/session", "unsafe")

    response = _post_account_onboarding_artifact(
        app_client,
        idempotency_key="artifact-unsafe-1",
        content_base64=base64.b64encode(buffer.getvalue()).decode("ascii"),
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "ONBOARDING_ARTIFACT_UNSAFE"
    assert "object_key" not in response.text


def test_account_onboarding_artifact_rejects_absolute_archive_paths(app_client) -> None:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("/tdlib/session", "unsafe")

    response = _post_account_onboarding_artifact(
        app_client,
        idempotency_key="artifact-absolute-1",
        content_base64=base64.b64encode(buffer.getvalue()).decode("ascii"),
    )

    assert response.status_code == 400
    assert response.json()["details"]["validation_code"] == "archive_rejected_unsafe_path"


def test_account_onboarding_artifact_rejects_invalid_base64(app_client) -> None:
    response = _post_account_onboarding_artifact(
        app_client,
        idempotency_key="artifact-invalid-base64",
        content_base64="not-base64!",
    )

    assert response.status_code == 422
    assert "content_base64" in response.text


def test_account_onboarding_artifact_rejects_archive_symlink(app_client) -> None:
    buffer = io.BytesIO()
    info = ZipInfo("tdlib/link")
    info.external_attr = 0o120777 << 16
    with ZipFile(buffer, "w") as archive:
        archive.writestr(info, "target")

    response = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "artifact-symlink",
            "source_type": "tdlib_directory",
            "filename": "tdlib.zip",
            "content_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
        },
    )

    assert response.status_code == 400
    assert response.json()["details"]["validation_code"] == "archive_rejected_symlink"


def test_account_onboarding_artifact_rejects_too_many_archive_files(
    app_client, monkeypatch
) -> None:
    monkeypatch.setattr(onboarding_artifacts, "MAX_ARCHIVE_FILES", 1)

    response = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "artifact-too-many-files",
            "source_type": "tdlib_directory",
            "filename": "tdlib.zip",
            "content_base64": base64.b64encode(_zip_bytes({"a": "1", "b": "2"})).decode("ascii"),
        },
    )

    assert response.status_code == 400
    assert response.json()["details"]["validation_code"] == "archive_rejected_too_many_files"


def test_account_onboarding_artifact_rejects_too_deep_archive(app_client, monkeypatch) -> None:
    monkeypatch.setattr(onboarding_artifacts, "MAX_ARCHIVE_DEPTH", 2)

    response = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "artifact-too-deep",
            "source_type": "tdlib_directory",
            "filename": "tdlib.zip",
            "content_base64": base64.b64encode(_zip_bytes({"a/b/c": "deep"})).decode("ascii"),
        },
    )

    assert response.status_code == 400
    assert response.json()["details"]["validation_code"] == "archive_rejected_too_deep"


def test_account_onboarding_artifact_rejects_too_large_uncompressed_archive(
    app_client, monkeypatch
) -> None:
    monkeypatch.setattr(onboarding_artifacts, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 4)

    response = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "artifact-too-large-expanded",
            "source_type": "tdlib_directory",
            "filename": "tdlib.zip",
            "content_base64": base64.b64encode(_zip_bytes({"tdlib/session": "too-large"})).decode(
                "ascii"
            ),
        },
    )

    assert response.status_code == 400
    assert response.json()["details"]["validation_code"] == "archive_rejected_too_large"


def test_account_onboarding_artifact_success_response_is_frontend_safe(app_client) -> None:
    encoded = base64.b64encode(b'{"session":"redacted fixture"}').decode("ascii")

    response = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "artifact-safe-response-1",
            "source_type": "session_file",
            "filename": "fixture.session.json",
            "content_base64": encoded,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "validated"
    assert "object_key" not in body
    assert "path" not in response.text


def test_account_onboarding_session_file_unknown_format_is_unsupported(app_client) -> None:
    upload = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "session-file-unknown-upload",
            "source_type": "session_file",
            "filename": "unknown.bin",
            "content_base64": base64.b64encode(b"unknown").decode("ascii"),
        },
    )
    artifact_id = upload.json()["id"]
    create = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "session-file-unknown-create",
            "source_type": "session_file",
            "artifact_id": artifact_id,
            "filename": "unknown.bin",
        },
    ).json()

    response = app_client.post(
        f"/api/account-onboarding-batches/{create['batch']['id']}/validate",
        json={"idempotency_key": "session-file-unknown-validate"},
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["status"] == "unsupported"
    assert item["validation_code"] == "session_file_unsupported"


def test_account_onboarding_json_metadata_scalar_is_blocked(app_client) -> None:
    create = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "metadata-invalid-create",
            "source_type": "json_metadata",
            "metadata_json": "not-an-object",
        },
    ).json()

    response = app_client.post(
        f"/api/account-onboarding-batches/{create['batch']['id']}/validate",
        json={"idempotency_key": "metadata-invalid-validate"},
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["status"] == "blocked"
    assert item["validation_code"] == "metadata_invalid"


def test_account_onboarding_default_tdlib_capability_is_not_full_support(app_client) -> None:
    response = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "tdlib-capability-create",
            "source_type": "phone",
            "phone_items": [{"phone_number": "+15550102000"}],
        },
    )

    assert response.status_code == 201
    capabilities = {item["source_type"]: item for item in response.json()["capabilities"]}
    assert capabilities["tdlib_directory"]["can_materialize_session"] is False
    assert capabilities["tdlib_directory"]["user_facing_support_level"] == "preview_only"


def test_account_onboarding_create_idempotency_conflict(app_client) -> None:
    payload = {
        "idempotency_key": "onboarding-create-conflict",
        "source_type": "phone",
        "phone_items": [{"phone_number": "+15550102000"}],
    }
    first = app_client.post("/api/account-onboarding-batches", json=payload)
    second = app_client.post(
        "/api/account-onboarding-batches",
        json={**payload, "phone_items": [{"phone_number": "+15550102001"}]},
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error_code"] == "ONBOARDING_INVALID_STATE"


def test_account_onboarding_queue_unavailable_persists_safe_failure(
    app_client, monkeypatch
) -> None:
    monkeypatch.setattr(onboarding_service, "enqueue_batch_items", lambda _batch: False)
    created = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "queue-unavailable-create",
            "source_type": "phone",
            "phone_items": [{"phone_number": "+15550102000"}],
        },
    ).json()
    batch_id = created["batch"]["id"]
    app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/validate",
        json={"idempotency_key": "queue-unavailable-validate"},
    )

    confirm = app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/confirm",
        json={
            "idempotency_key": "queue-unavailable-confirm",
            "confirmation": "ADD_ACCOUNTS",
            "consent_accepted": True,
            "consent_version": "v1",
        },
    )
    detail = app_client.get(f"/api/account-onboarding-batches/{batch_id}")

    assert confirm.status_code == 503
    assert detail.json()["batch"]["status"] == "failed"
    assert detail.json()["items"][0]["status"] == "failed"
    assert "next_retry_at" in detail.json()["items"][0]
    assert "phone_number" not in detail.text


def test_account_onboarding_retry_denied_when_cooldown_active(app_client, db_session) -> None:
    created = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "retry-cooldown-create",
            "source_type": "phone",
            "phone_items": [{"phone_number": "+15550102000"}],
        },
    ).json()
    item_id = created["items"][0]["id"]
    item = db_session.get(AccountOnboardingItem, item_id)
    assert item is not None
    item.status = "failed"
    item.last_error_code = "tdlib_unavailable"
    item.next_retry_at = utc_now() + timedelta(seconds=60)
    db_session.commit()

    response = app_client.post(
        f"/api/account-onboarding-batches/{created['batch']['id']}/items/{item_id}/retry",
        json={"idempotency_key": "retry-cooldown-attempt"},
    )

    assert response.status_code == 429
    assert response.json()["error_code"] == "ONBOARDING_RATE_LIMITED"
    assert response.json()["details"]["retry_after_seconds"] > 0
    assert response.json()["details"]["request_id"] == response.json()["request_id"]


def test_account_onboarding_phone_execution_links_backend_auth_session(
    app_client, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(onboarding_service, "enqueue_batch_items", lambda _batch: True)
    created = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "auth-session-link-create",
            "source_type": "phone",
            "phone_items": [{"phone_number": "+15550102000", "label": "Primary"}],
        },
    ).json()
    batch_id = created["batch"]["id"]
    app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/validate",
        json={"idempotency_key": "auth-session-link-validate"},
    )
    confirmed = app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/confirm",
        json={
            "idempotency_key": "auth-session-link-confirm",
            "confirmation": "ADD_ACCOUNTS",
            "consent_accepted": True,
            "consent_version": "v1",
        },
    ).json()
    item_id = confirmed["items"][0]["id"]

    item = onboarding_service.execute_item(db_session, item_id=item_id)
    assert item.auth_session_id is not None
    auth_session = db_session.get(TelegramAuthSession, item.auth_session_id)
    assert auth_session is not None
    assert auth_session.source == "account_onboarding"
    assert auth_session.requires_code is True
    assert auth_session.tdlib_storage_key is not None

    detail = app_client.get(f"/api/account-onboarding-batches/{batch_id}")
    body = detail.json()
    assert body["items"][0]["auth_session_id"] == auth_session.id
    assert "tdlib_storage_key" not in detail.text

    code = app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/items/{item_id}/code",
        json={"idempotency_key": "auth-session-link-code", "code": "12345"},
    )
    db_session.refresh(auth_session)

    assert code.status_code == 200
    assert auth_session.status == "checking_session"
    assert auth_session.requires_code is False
    assert "12345" not in code.text


def test_account_onboarding_tdlib_preview_requires_reauth_without_verifier(
    app_client, monkeypatch
) -> None:
    monkeypatch.setattr(onboarding_service, "enqueue_batch_items", lambda _batch: True)
    upload = app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": "tdlib-exec-upload",
            "source_type": "tdlib_directory",
            "filename": "tdlib.zip",
            "content_base64": base64.b64encode(_zip_bytes({"tdlib/session": "safe"})).decode(
                "ascii"
            ),
        },
    ).json()
    created = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "tdlib-exec-create",
            "source_type": "tdlib_directory",
            "artifact_id": upload["id"],
            "filename": "tdlib.zip",
        },
    ).json()
    batch_id = created["batch"]["id"]
    validated = app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/validate",
        json={"idempotency_key": "tdlib-exec-validate"},
    ).json()
    assert validated["items"][0]["status"] == "requires_reauth"
    assert validated["items"][0]["validation_code"] == "tdlib_artifact_verifier_not_enabled"
    confirmed = app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/confirm",
        json={
            "idempotency_key": "tdlib-exec-confirm",
            "confirmation": "ADD_ACCOUNTS",
            "consent_accepted": True,
            "consent_version": "v1",
        },
    ).json()
    detail = app_client.get(f"/api/account-onboarding-batches/{batch_id}")

    assert confirmed["batch"]["status"] == "failed"
    assert detail.json()["items"][0]["status"] == "requires_reauth"
    assert detail.json()["items"][0]["validation_code"] == "tdlib_artifact_verifier_not_enabled"
    assert "object_key" not in detail.text
    assert "tdlib/session" not in detail.text


def test_account_onboarding_expire_artifacts_marks_metadata_only(db_session) -> None:
    batch = AccountOnboardingBatch(
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        source_type="tdlib_directory",
        status="preview_ready",
        idempotency_key="artifact-expiry-batch",
        payload_hash="hash",
    )
    artifact = AccountOnboardingArtifact(
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        batch=batch,
        source_type="tdlib_directory",
        object_key="account-onboarding/workspace/artifact/private-key",
        sha256="0" * 64,
        size_bytes=10,
        content_type_detected="application/zip",
        status="validated",
        expires_at=utc_now() - timedelta(seconds=1),
    )
    db_session.add_all([batch, artifact])
    db_session.commit()

    expired = onboarding_service.expire_artifacts(db_session)

    assert expired == 1
    assert artifact.status == "expired"
    assert artifact.failure_code == "artifact_expired"
    events = db_session.query(AccountOnboardingEvent).filter_by(batch_id=batch.id).all()
    assert events
    assert "private-key" not in repr([event.safe_payload_json for event in events])


def _zip_bytes(entries: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _post_account_onboarding_artifact(
    app_client,
    *,
    idempotency_key: str,
    content_base64: str,
    source_type: str = "tdlib_directory",
    filename: str = "tdlib.zip",
):
    return app_client.post(
        "/api/account-onboarding-artifacts",
        json={
            "idempotency_key": idempotency_key,
            "source_type": source_type,
            "filename": filename,
            "content_base64": content_base64,
        },
    )


def test_account_onboarding_submit_code_is_idempotent_and_redacted(app_client, db_session) -> None:
    created = app_client.post(
        "/api/account-onboarding-batches",
        json={
            "idempotency_key": "onboarding-code-create",
            "source_type": "phone",
            "phone_items": [{"phone_number": "+15550102000"}],
        },
    ).json()
    batch_id = created["batch"]["id"]
    app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/validate",
        json={"idempotency_key": "onboarding-code-validate"},
    )
    item_id = created["items"][0]["id"]
    item = db_session.get(AccountOnboardingItem, item_id)
    assert item is not None
    item.status = "waiting_code"
    db_session.commit()

    body = {"idempotency_key": "onboarding-code-submit", "code": "12345"}
    first = app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/items/{item_id}/code",
        json=body,
    )
    second = app_client.post(
        f"/api/account-onboarding-batches/{batch_id}/items/{item_id}/code",
        json=body,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == second.json()["status"] == "checking_session"
    events = db_session.query(AccountOnboardingEvent).all()
    assert "12345" not in repr([event.safe_payload_json for event in events])


def test_account_onboarding_detail_is_workspace_scoped(app_client, db_session) -> None:
    foreign_workspace = Workspace(
        name="Foreign onboarding",
        slug="foreign-onboarding",
        owner_user_id=DEFAULT_LOCAL_USER_ID,
    )
    db_session.add(foreign_workspace)
    db_session.flush()
    batch = AccountOnboardingBatch(
        workspace_id=foreign_workspace.id,
        source_type="phone_bulk",
        status="preview_ready",
        label="Foreign",
        idempotency_key="foreign-onboarding-batch",
        payload_hash="hash",
    )
    db_session.add(batch)
    db_session.commit()

    response = app_client.get(f"/api/account-onboarding-batches/{batch.id}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "ONBOARDING_BATCH_NOT_FOUND"
