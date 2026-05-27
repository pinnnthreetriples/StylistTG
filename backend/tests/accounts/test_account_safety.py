from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from freezegun import freeze_time
from sqlalchemy import select

from app.db import Base
from app.main import app
from app.models import (
    AccountOperationLog,
    AccountOperationCooldown,
    AccountProxy,
    AccountProfileState,
    AccountState,
    AccountStoryPost,
    JobState,
)
from app.services.accounts import create_account
from app.services.database import create_sqlite_test_session_factory

from conftest import override_app_session, seed_audio_asset, seed_job, seed_story_asset
from tests.helpers.factories import seed_failed_step, seed_operation_cooldown


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Guarantee dependency_overrides are cleaned up after every test."""
    yield
    app.dependency_overrides.clear()


def _ready_account(db_session, external_ref: str, *, first_name: str = "Stylist"):
    """Create an EXECUTION_USABLE account with profile state."""
    account = create_account(db_session, external_ref=external_ref)
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.runtime_health = "ready"
    account.profile_state = AccountProfileState(account_id=account.id, first_name=first_name)
    return account


def _setup_account_with_flood_wait(db_session, *, external_ref: str):
    """Create an EXECUTION_USABLE account with a failed FLOOD_WAIT_60 username step."""
    account = _ready_account(db_session, external_ref)
    finished_at = datetime.now(UTC)
    job = seed_job(
        db_session,
        account_id=account.id,
        payload={"username": "name"},
        state=JobState.FAILED,
        finished_at=finished_at,
    )
    seed_failed_step(db_session, job_id=job.id, finished_at=finished_at)
    return account


def test_account_safety_ready_for_execution_usable_account(db_session) -> None:
    from app.services.account_safety import build_account_safety

    account = _ready_account(db_session, "+15550102000")
    account.runtime_state.session_present = True
    account.runtime_state.reauth_required = False
    db_session.commit()

    safety = build_account_safety(db_session, account.id)

    assert safety["health_status"] == "ready"
    assert safety["overall_risk_level"] == "low"
    assert safety["capabilities"]["profile_text"]["state"] == "available"
    assert safety["risk_by_operation"]["profile_update"]["level"] == "low"


def test_operation_log_sanitizes_secrets(db_session) -> None:
    from app.services.operation_logs import log_operation, operation_log_to_dict

    account = create_account(db_session, external_ref="+15550103000")
    row = log_operation(
        db_session,
        account_id=account.id,
        operation_type="proxy",
        operation_key="save_proxy",
        status="completed",
        source="test",
        message="saved",
        metadata={
            "password": "secret",
            "nested": {"api_hash": "secret"},
            "proxyPassword": "secret",
            "items": [{"operator_api_token": "secret"}],
        },
    )
    db_session.commit()

    payload = operation_log_to_dict(row)

    assert payload["metadata"]["password"] == "***"
    assert payload["metadata"]["nested"]["api_hash"] == "***"
    assert payload["metadata"]["proxyPassword"] == "***"
    assert payload["metadata"]["items"][0]["operator_api_token"] == "***"
    assert payload["metadata"]["items"][0]["operator_api_token"] == "***"


def test_proxy_password_requires_encryption_key(db_session) -> None:
    from app.config import Settings
    from app.services.proxy_accounts import upsert_account_proxy

    account = create_account(db_session, external_ref="+15550103001")
    config = Settings(proxy_credentials_encryption_key=None)

    try:
        upsert_account_proxy(
            db_session,
            account.id,
            proxy_type="socks5",
            host="127.0.0.1",
            port=1080,
            username="user",
            password="secret",
            config=config,
        )
    except ValueError as exc:
        assert str(exc) in {
            "proxy_credentials_key_required",
            "proxy_credentials_crypto_unavailable",
        }
    else:
        raise AssertionError("proxy password must not be stored without encryption")


def test_proxy_check_updates_status_and_writes_operation_log(db_session) -> None:
    from app.services.proxy_checks import check_account_proxy

    class FakeChecker:
        def check(self, _proxy):
            return False, "proxy_timeout", "timeout"

    account = create_account(db_session, external_ref="+15550103002")
    db_session.add(
        AccountProxy(account_id=account.id, proxy_type="http", host="127.0.0.1", port=8080)
    )
    db_session.commit()

    result = check_account_proxy(db_session, account.id, checker=FakeChecker())
    log = (
        db_session.execute(
            select(AccountOperationLog).where(AccountOperationLog.account_id == account.id)
        )
        .scalars()
        .first()
    )

    assert result["status"] == "failed"
    assert result["last_error_code"] == "proxy_timeout"
    assert log is not None
    assert log.operation_type == "proxy"
    assert log.status == "failed"


def test_operation_logs_api_returns_account_and_global_pages() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        from app.services.operation_logs import log_operation

        account = create_account(session, external_ref="+15550103003")
        log_operation(
            session,
            account_id=account.id,
            operation_type="validity_check",
            status="completed",
            source="test",
            message="checked",
        )
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    client = TestClient(app)

    account_response = client.get(f"/api/accounts/{account_id}/operation-logs")
    global_response = client.get("/api/operation-logs")

    app.dependency_overrides.clear()

    assert account_response.status_code == 200
    assert account_response.json()["items"][0]["operation_type"] == "validity_check"
    assert global_response.status_code == 200
    assert global_response.json()["total"] == 1


def test_proxy_api_does_not_return_password() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = create_account(session, external_ref="+15550103004")
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.put(
        f"/api/accounts/{account_id}/proxy",
        json={"proxy_type": "http", "host": "127.0.0.1", "port": 8080, "username": "user"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["has_password"] is False
    assert "password" not in payload


def test_proxy_check_keeps_known_not_configured_error_safe() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = create_account(session, external_ref="+15550103005")
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.post(f"/api/accounts/{account_id}/proxy/check")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error_code"] == "PROXY_NOT_CONFIGURED"
    assert response.json()["message"] == "proxy not configured"


def test_proxy_check_hides_unknown_value_error_text(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = create_account(session, external_ref="+15550103006")
        account_id = account.id
        session.commit()

    def _raise_internal_error(*_args, **_kwargs):
        raise ValueError("socket failed for proxy password secret")

    override_app_session(session_factory)
    monkeypatch.setattr("app.api.account_proxy_routes.check_account_proxy", _raise_internal_error)
    client = TestClient(app)

    response = client.post(f"/api/accounts/{account_id}/proxy/check")

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["error_code"] == "PROXY_CHECK_FAILED"
    assert response.json()["message"] == "Proxy check failed"
    assert "secret" not in response.text


def test_account_safety_blocked_by_reauth_required(db_session) -> None:
    from app.services.account_safety import build_account_safety

    account = create_account(db_session, external_ref="+15550102001")
    account.account_state = AccountState.REAUTH_REQUIRED
    account.runtime_state.runtime_health = "closed"
    account.runtime_state.reauth_required = True
    db_session.commit()

    safety = build_account_safety(db_session, account.id)

    assert safety["health_status"] == "blocked"
    assert safety["overall_risk_level"] == "blocked"
    assert safety["capabilities"]["profile_text"]["state"] == "blocked"
    assert safety["risk_by_operation"]["story_post"]["level"] == "blocked"
    assert "reauth_required" in [reason["code"] for reason in safety["reasons"]]


@freeze_time("2026-01-15 12:00:00")
def test_account_safety_attention_for_recent_partial_job(db_session) -> None:
    from app.services.account_safety import build_account_safety

    account = _ready_account(db_session, "+15550102002")
    seed_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist"},
        state=JobState.PARTIALLY_COMPLETED,
        finished_at=datetime.now(UTC),
    )
    db_session.commit()

    safety = build_account_safety(db_session, account.id)

    assert safety["health_status"] == "attention"
    assert safety["risk_by_operation"]["profile_update"]["level"] == "medium"
    assert "recent_partial_job" in [reason["code"] for reason in safety["reasons"]]


def test_account_safety_story_live_disabled_and_music_unknown(db_session) -> None:
    from app.services.account_safety import build_account_safety

    account = _ready_account(db_session, "+15550102003")
    db_session.commit()

    safety = build_account_safety(db_session, account.id)

    assert safety["capabilities"]["story_post"]["state"] == "blocked"
    assert safety["capabilities"]["profile_music"]["state"] == "unknown"
    assert safety["risk_by_operation"]["story_post"]["level"] == "blocked"


@freeze_time("2026-01-15 12:00:00")
def test_account_safety_high_risk_for_recent_flood_wait(db_session) -> None:
    from app.services.account_safety import build_account_safety

    account = _ready_account(db_session, "+15550102004")
    job = seed_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist"},
        state=JobState.FAILED,
        finished_at=datetime.now(UTC),
    )
    seed_failed_step(db_session, job_id=job.id, step_key="set_name", step_type="set_name")

    safety = build_account_safety(db_session, account.id)

    assert safety["risk_by_operation"]["profile_update"]["level"] == "blocked"
    assert "recent_flood_wait" in [reason["code"] for reason in safety["reasons"]]


def test_account_safety_summary_and_detail_endpoints() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = _ready_account(session, "+15550102005")
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    client = TestClient(app)

    summary = client.get("/api/accounts/safety-summary")
    detail = client.get(f"/api/accounts/{account_id}/safety")

    app.dependency_overrides.clear()

    assert summary.status_code == 200
    assert summary.json()[0]["account_id"] == account_id
    assert summary.json()[0]["health_status"] == "ready"
    assert detail.status_code == 200
    assert detail.json()["account_id"] == account_id
    assert "profile_text" in detail.json()["capabilities"]


def test_account_validity_check_db_snapshot_persists_run_and_snapshot() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = _ready_account(session, "+15550102007")
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.post(
        f"/api/accounts/{account_id}/validity-check", json={"mode": "db_snapshot"}
    )
    checks = client.get(f"/api/accounts/{account_id}/validity-checks")
    safety = client.get(f"/api/accounts/{account_id}/safety")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["mode"] == "db_snapshot"
    assert response.json()["status"] == "completed"
    assert response.json()["result"]["health_status"] == "ready"
    assert checks.status_code == 200
    assert checks.json()[0]["status"] == "completed"
    assert safety.json()["last_validity_check"]["status"] == "completed"


def test_account_validity_check_tdlib_mode_is_safe_unsupported_without_live_action() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = create_account(session, external_ref="+15550102008")
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.post(
        f"/api/accounts/{account_id}/validity-check", json={"mode": "tdlib_readonly"}
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] in {"completed", "unsupported"}
    if response.json()["status"] == "completed":
        assert response.json()["result"]["validity_status"] in {
            "runtime_broken",
            "reauth_required",
            "unknown",
        }
    else:
        assert response.json()["error_code"] == "TDLIB_READONLY_CHECK_NOT_ENABLED"


def test_account_validity_check_hides_unknown_value_error_text(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = _ready_account(session, "+15550102025")
        account_id = account.id
        session.commit()

    def _raise_internal_error(*_args, **_kwargs):
        raise ValueError("tdlib runtime leaked /home/app/.tdlib/session")

    override_app_session(session_factory)
    monkeypatch.setattr(
        "app.api.account_safety_routes.run_account_validity_check", _raise_internal_error
    )
    client = TestClient(app)

    response = client.post(
        f"/api/accounts/{account_id}/validity-check", json={"mode": "db_snapshot"}
    )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["error_code"] == "VALIDITY_CHECK_FAILED"
    assert response.json()["message"] == "Account validity check failed"
    assert "tdlib" not in response.text
    assert ".tdlib" not in response.text


def test_account_validity_tdlib_readonly_adapter_returns_valid_and_does_not_write(
    db_session,
) -> None:
    from app.services.account_validity import run_account_validity_check

    class FakeReadonlyAdapter:
        def __init__(self) -> None:
            self.write_calls: list[str] = []

        def check_account(self, account_id: str) -> dict:
            return {
                "status": "valid",
                "telegram_user_id": "123456",
                "runtime_health": "ready",
                "profile": {"first_name": "Stylist", "username": "stylisttg"},
            }

        def set_name(self, *_args, **_kwargs) -> None:
            self.write_calls.append("set_name")

    account = create_account(db_session, external_ref="+15550102010")
    adapter = FakeReadonlyAdapter()

    result = run_account_validity_check(
        db_session, account.id, mode="tdlib_readonly", adapter=adapter
    )

    assert result["status"] == "completed"
    assert result["result"]["validity_status"] == "valid"
    assert adapter.write_calls == []
    assert account.account_state == AccountState.EXECUTION_USABLE
    assert account.runtime_state.runtime_health == "ready"
    assert account.profile_state.username == "stylisttg"


def test_account_validity_tdlib_readonly_adapter_create_failure_is_structured() -> None:
    from app.adapters.tdlib_readonly_validity import TdlibReadOnlyValidityAdapter
    from app.config import Settings

    class RaisingFactory:
        def create(self, account_id: str):
            raise OSError("tdjson unavailable")

    adapter = TdlibReadOnlyValidityAdapter(
        client_factory=RaisingFactory(),
        config=Settings(tdlib_api_id=1, tdlib_api_hash="hash", tdlib_auth_timeout_seconds=0.01),
    )

    result = adapter.check_account("account-1")

    assert result["status"] == "runtime_broken"
    assert result["error_code"] == "tdlib_readonly_runtime_broken"
    assert result["error_class"] == "runtime"
    assert result["error"] == "internal_error"


@freeze_time("2026-01-15 12:00:00")
def test_account_safety_reports_recent_flood_wait_without_writing_on_read(db_session) -> None:
    from app.services.account_safety import build_account_safety

    account = _setup_account_with_flood_wait(db_session, external_ref="+15550102011")

    safety = build_account_safety(db_session, account.id)

    cooldown = safety["cooldowns_by_operation"]["username"][0]
    assert cooldown["level"] == "blocked"
    assert cooldown["reason_code"] == "recent_flood_wait"
    assert cooldown["retry_after_at"] > datetime.now(UTC)
    assert safety["risk_by_operation"]["username"]["level"] == "blocked"
    persisted = (
        db_session.execute(
            select(AccountOperationCooldown).where(
                AccountOperationCooldown.account_id == account.id
            )
        )
        .scalars()
        .all()
    )
    assert persisted == []


@freeze_time("2026-01-15 12:00:00")
def test_validity_check_persists_operation_cooldown_from_flood_wait(db_session) -> None:
    from app.services.account_validity import run_account_validity_check

    account = _setup_account_with_flood_wait(db_session, external_ref="+15550102021")

    run_account_validity_check(db_session, account.id)

    persisted = (
        db_session.execute(
            select(AccountOperationCooldown).where(
                AccountOperationCooldown.account_id == account.id
            )
        )
        .scalars()
        .all()
    )
    assert len(persisted) == 1
    assert persisted[0].operation == "username"


@freeze_time("2026-01-15 12:00:00")
def test_expired_operation_cooldown_no_longer_blocks_safety(db_session) -> None:
    from app.services.account_safety import build_account_safety

    account = _ready_account(db_session, "+15550102012")
    db_session.add(
        AccountOperationCooldown(
            account_id=account.id,
            operation="username",
            level="blocked",
            reason_code="recent_flood_wait",
            started_at=datetime.now(UTC) - timedelta(minutes=10),
            retry_after_at=datetime.now(UTC) - timedelta(minutes=1),
            source="job_step_result",
        )
    )
    db_session.commit()

    safety = build_account_safety(db_session, account.id)

    assert safety["cooldowns_by_operation"]["username"] == []
    assert safety["risk_by_operation"]["username"]["level"] != "blocked"


@freeze_time("2026-01-15 12:00:00")
def test_account_update_preview_blocks_only_affected_cooldown_operation(db_session) -> None:
    from app.services.account_update_jobs import build_account_update_preview

    account = _ready_account(db_session, "+15550102013")
    seed_operation_cooldown(db_session, account_id=account.id)

    bio_preview = build_account_update_preview(
        db_session,
        account_id=account.id,
        desired_state={"profile": {"bio": "safe"}},
    )
    username_preview = build_account_update_preview(
        db_session,
        account_id=account.id,
        desired_state={"profile": {"username": "blocked_name"}},
    )

    assert bio_preview["can_create_job"] is True
    assert "cooldown_active:username" not in bio_preview["safety_blockers"]
    assert username_preview["can_create_job"] is False
    assert "cooldown_active:username" in username_preview["safety_blockers"]


def _safety_and_preview(db_session, account_id, desired_state, **settings_kwargs):
    """Build safety + preview fields with a single Settings instance."""
    from app.config import Settings
    from app.services.account_safety import build_account_safety, safety_preview_fields_with_policy

    config = Settings(**settings_kwargs)
    safety = build_account_safety(db_session, account_id, config=config)
    fields = safety_preview_fields_with_policy(safety, desired_state, config=config)
    return safety, fields


def test_safety_preview_respects_unknown_capability_policy(db_session) -> None:
    account = _ready_account(db_session, "+15550102014")
    db_session.commit()

    _safety, fields = _safety_and_preview(
        db_session,
        account.id,
        {"profile_audio": {"action": "add", "audio_asset_id": "asset-1"}},
        unknown_capability_policy="block_live_execution",
    )

    assert "music_capability_not_checked" in fields["safety_blockers"]


def test_safety_preview_requires_fresh_validity_for_live_policy(db_session) -> None:
    account = _ready_account(db_session, "+15550102015")
    db_session.commit()

    _safety, fields = _safety_and_preview(
        db_session,
        account.id,
        {"profile": {"bio": "updated"}},
        fresh_validity_required="always_for_live",
    )

    assert "fresh_validity_required" in fields["safety_blockers"]
    assert fields["operation_safety"][0]["operation"] == "profile_update"
    assert fields["operation_safety"][0]["can_override"] is True


def test_safety_override_with_reason_allows_overridable_preview_blocker(db_session) -> None:
    from app.config import Settings
    from app.services.account_safety import build_account_safety, safety_preview_fields_with_policy
    from app.services.account_safety_overrides import create_safety_override

    account = _ready_account(db_session, "+15550102022")
    db_session.commit()
    create_safety_override(
        db_session,
        account.id,
        workspace_id=account.workspace_id,
        operation="profile_music",
        reason="Оператор проверил файл и принимает предупреждение",
        requested_blockers=["music_capability_not_checked"],
    )

    safety = build_account_safety(
        db_session, account.id, config=Settings(unknown_capability_policy="block_live_execution")
    )
    fields = safety_preview_fields_with_policy(
        safety,
        {"profile_audio": {"action": "add", "audio_asset_id": "asset-1"}},
        config=Settings(unknown_capability_policy="block_live_execution"),
    )

    assert "music_capability_not_checked" not in fields["safety_blockers"]
    assert "override_applied:profile_music" in fields["safety_warnings"]
    assert fields["operation_safety"][0]["state"] == "warning"


def test_safety_override_rejects_non_overridable_blocker(db_session) -> None:
    from app.services.account_safety_overrides import create_safety_override

    account = create_account(db_session, external_ref="+15550102023")
    db_session.commit()

    try:
        create_safety_override(
            db_session,
            account.id,
            workspace_id=account.workspace_id,
            operation="profile_update",
            reason="try hard override",
            requested_blockers=["reauth_required"],
        )
    except ValueError as exc:
        assert "non-overridable blocker" in str(exc)
    else:
        raise AssertionError("override should reject non-overridable blockers")


def test_safety_override_service_requires_matching_workspace(db_session) -> None:
    from app.models import User, Workspace, WorkspaceMember, WorkspacePlan
    from app.services.account_safety_overrides import create_safety_override

    account = create_account(db_session, external_ref="+15550102024")
    user = User(
        email="foreign-override@example.test",
        external_auth_provider="test",
        external_auth_user_id="foreign-override",
        status="active",
    )
    db_session.add(user)
    db_session.flush()
    workspace = Workspace(
        name="foreign override", slug="foreign-override", owner_user_id=user.id, status="active"
    )
    db_session.add(workspace)
    db_session.flush()
    db_session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    db_session.add(WorkspacePlan(workspace_id=workspace.id))
    db_session.commit()

    try:
        create_safety_override(
            db_session,
            account.id,
            workspace_id=workspace.id,
            operation="profile_update",
            reason="wrong tenant",
            requested_blockers=["fresh_validity_required"],
        )
    except ValueError as exc:
        assert str(exc) == "account not found"
    else:
        raise AssertionError("override should require matching workspace")


@freeze_time("2026-01-15 12:00:00")
def test_recent_failure_policy_creates_warning_cooldown_for_soft_failure(db_session) -> None:
    from app.config import Settings
    from app.services.account_safety import build_account_safety

    account = _ready_account(db_session, "+15550102020")
    finished_at = datetime.now(UTC)
    job = seed_job(
        db_session,
        account_id=account.id,
        payload={"username": "taken"},
        state=JobState.FAILED,
        finished_at=finished_at,
    )
    seed_failed_step(
        db_session, job_id=job.id, error_code="USERNAME_INVALID", finished_at=finished_at
    )

    safety = build_account_safety(
        db_session,
        account.id,
        config=Settings(recent_failure_policy="cooldown", username_cooldown_seconds=900),
    )

    cooldown = safety["cooldowns_by_operation"]["username"][0]
    assert cooldown["level"] == "warning"
    assert cooldown["reason_code"] == "recent_failure_cooldown"


@freeze_time("2026-01-15 12:00:00")
def test_account_capabilities_deepen_story_delete_and_username_failure(db_session) -> None:
    from app.services.account_safety import build_account_safety

    account = _ready_account(db_session, "+15550102009")
    db_session.add(
        AccountStoryPost(
            account_id=account.id,
            media_kind="image",
            status="posted",
            can_be_deleted=False,
            posted_at=datetime.now(UTC),
        )
    )
    job = seed_job(
        db_session,
        account_id=account.id,
        payload={"username": "taken"},
        state=JobState.FAILED,
        finished_at=datetime.now(UTC),
    )
    seed_failed_step(db_session, job_id=job.id, error_code="USERNAME_INVALID")

    safety = build_account_safety(db_session, account.id)

    assert safety["capabilities"]["story_delete"]["state"] == "limited"
    assert "story_delete_not_confirmed" in safety["capabilities"]["story_delete"]["reason_codes"]
    assert safety["risk_by_operation"]["username"]["level"] == "medium"


def test_account_update_preview_includes_safety_fields_and_preserves_steps(db_session) -> None:
    from app.services.account_update_jobs import build_account_update_preview

    account = _ready_account(db_session, "+15550102006")
    audio = seed_audio_asset(db_session)
    story = seed_story_asset(db_session)
    db_session.commit()

    preview = build_account_update_preview(
        db_session,
        account_id=account.id,
        desired_state={
            "profile": {"name": "Stylist", "username": "stylisttg"},
            "profile_audio": {"action": "add", "audio_asset_id": audio.id},
            "stories": [{"action": "post_image", "asset_id": story.id}],
        },
    )

    assert "account_safety" in preview
    assert "risk_by_operation" in preview
    assert preview["safety_blockers"]
    assert "stories_mock_mode" in preview["safety_blockers"]
    assert "add_profile_audio" in [step["step_type"] for step in preview["steps"]]
    assert "post_story_image" in [step["step_type"] for step in preview["steps"]]


def test_account_batch_safety_preview_blocks_accounts_with_hard_safety_state(db_session) -> None:
    from app.services.account_batch_safety import build_account_batch_safety_preview

    ready = create_account(db_session, external_ref="+15550102016")
    ready.account_state = AccountState.EXECUTION_USABLE
    ready.runtime_state.runtime_health = "ready"
    ready.profile_state = AccountProfileState(account_id=ready.id, first_name="Ready")

    blocked = create_account(db_session, external_ref="+15550102017")
    blocked.account_state = AccountState.REAUTH_REQUIRED
    blocked.runtime_state.runtime_health = "closed"
    blocked.runtime_state.reauth_required = True
    db_session.commit()

    preview = build_account_batch_safety_preview(
        db_session,
        account_ids=[ready.id, blocked.id],
        operation="profile_update",
    )

    assert preview["can_start"] is False
    assert preview["counts"]["ready"] == 1
    assert preview["counts"]["needs_login"] == 1
    assert blocked.id in preview["blocking_account_ids"]


@freeze_time("2026-01-15 12:00:00")
def test_account_batch_safety_preview_marks_operation_cooldown_as_paused(db_session) -> None:
    from app.services.account_batch_safety import build_account_batch_safety_preview

    account = _ready_account(db_session, "+15550102018", first_name="Paused")
    seed_operation_cooldown(db_session, account_id=account.id)

    preview = build_account_batch_safety_preview(
        db_session,
        account_ids=[account.id],
        operation="username",
    )

    assert preview["can_start"] is False
    assert preview["counts"]["paused"] == 1
    assert preview["items"][0]["batch_status"] == "paused"


def test_account_batch_safety_preview_endpoint_returns_counts() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = _ready_account(session, "+15550102019", first_name="Ready")
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.post(
        "/api/accounts/safety-batch-preview",
        json={"account_ids": [account_id], "operation": "profile_update"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["can_start"] is True
    assert response.json()["counts"]["ready"] == 1


def test_account_safety_override_endpoint_records_audit_entry() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = create_account(session, external_ref="+15550102024")
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.post(
        f"/api/accounts/{account_id}/safety-overrides",
        json={
            "operation": "profile_music",
            "reason": "Оператор проверил предупреждение",
            "requested_blockers": ["music_capability_not_checked"],
        },
    )
    rejected = client.post(
        f"/api/accounts/{account_id}/safety-overrides",
        json={
            "operation": "profile_update",
            "reason": "Нельзя обходить вход",
            "requested_blockers": ["reauth_required"],
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["requested_blockers"] == ["music_capability_not_checked"]
    assert rejected.status_code == 400
