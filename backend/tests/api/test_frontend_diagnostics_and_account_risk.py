from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from freezegun import freeze_time

from app.db import Base
from app.main import app
from app.models import (
    AccountOperationCooldown,
    AccountProfileState,
    AccountProxy,
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    User,
    Workspace,
    WorkspaceMember,
    WorkspacePlan,
)
from app.services.accounts import create_account
from app.services.auth_context import AuthContext, get_current_auth_context
from app.services.database import create_sqlite_test_session_factory

from conftest import override_app_session


# test-analyzer: disable=TQA004 reason="PII/leak contract test — verifies many fields are absent from safe summary"
def test_frontend_diagnostics_summary_is_safe(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.diagnostics.build_runtime_diagnostics",
        lambda: {"database": "ok", "redis": "ok", "tdlib": "not_configured"},
    )
    monkeypatch.setattr(
        "app.services.frontend_diagnostics.settings.app_env", "staging", raising=False
    )
    monkeypatch.setattr(
        "app.services.frontend_diagnostics.settings.auth_mode", "supabase_jwt", raising=False
    )
    monkeypatch.setattr(
        "app.services.frontend_diagnostics.settings.db_connection_mode", "neon", raising=False
    )
    monkeypatch.setattr(
        "app.services.frontend_diagnostics.settings.redis_url",
        "rediss://:secret@example.test/0",
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.frontend_diagnostics.settings.storage_backend", "s3", raising=False
    )
    monkeypatch.setattr(
        "app.services.frontend_diagnostics.settings.storage_s3_bucket", "bucket", raising=False
    )
    monkeypatch.setattr(
        "app.services.frontend_diagnostics.settings.storage_s3_access_key_id",
        "key-id",
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.frontend_diagnostics.settings.storage_s3_secret_access_key",
        "secret-key",
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.frontend_diagnostics.settings.tdlib_database_root",
        "C:/real/session/db",
        raising=False,
    )
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="local-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="owner",
        auth_source="test",
    )

    try:
        response = TestClient(app).get("/diagnostics/frontend-summary")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["app_env"] == "staging"
    assert payload["auth_mode"] == "supabase_jwt"
    assert payload["db"] == {"status": "ok", "mode": "neon"}
    assert payload["redis"] == {"status": "ok", "configured": True}
    assert payload["storage"]["backend"] == "s3"
    assert payload["storage"]["bucket_configured"] is True
    assert payload["tdlib"]["status"] == "not_configured"
    assert payload["tdlib"]["profile_execution_adapter"] == "mock"
    assert payload["tdlib"]["live_enabled"] is False
    assert {"profile_jobs", "auth_jobs", "account_lifecycle_jobs"}.issubset(
        set(payload["workers"]["queues"])
    )

    serialized = str(payload)
    assert "secret" not in serialized.lower()
    assert "rediss://" not in serialized
    assert "session/db" not in serialized
    assert "key-id" not in serialized


def test_account_risk_endpoint_scores_healthy_account_low() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        account.account_state = AccountState.EXECUTION_USABLE
        account.runtime_state.session_present = True
        account.runtime_state.runtime_health = "ready"
        account.runtime_state.reauth_required = False
        account.profile_state = AccountProfileState(account_id=account.id, first_name="Ready")
        session.commit()
        account_id = account.id

    override_app_session(session_factory)
    try:
        response = TestClient(app).get(f"/api/accounts/{account_id}/risk")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["account_id"] == account_id
    assert payload["score"] <= 24
    assert payload["level"] == "low"
    assert payload["reasons"][0]["code"] == "ready"
    assert payload["computed_at"]


def test_account_risk_endpoint_scores_reauth_and_missing_session_high() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        reauth = create_account(session, external_ref="+15550102001")
        reauth.account_state = AccountState.REAUTH_REQUIRED
        reauth.runtime_state.session_present = False
        reauth.runtime_state.runtime_health = "closed"
        reauth.runtime_state.reauth_required = True

        missing = create_account(session, external_ref="+15550102002")
        missing.account_state = AccountState.EXECUTION_USABLE
        missing.runtime_state.session_present = False
        missing.runtime_state.runtime_health = "ready"
        missing.runtime_state.reauth_required = False
        session.commit()
        reauth_id = reauth.id
        missing_id = missing.id

    override_app_session(session_factory)
    client = TestClient(app)
    try:
        reauth_response = client.get(f"/api/accounts/{reauth_id}/risk")
        missing_response = client.get(f"/api/accounts/{missing_id}/risk")
    finally:
        app.dependency_overrides.clear()

    assert reauth_response.status_code == 200
    assert reauth_response.json()["level"] == "critical"
    assert "reauth_required" in {reason["code"] for reason in reauth_response.json()["reasons"]}
    assert missing_response.status_code == 200
    assert missing_response.json()["level"] in {"high", "critical"}
    assert "missing_session" in {reason["code"] for reason in missing_response.json()["reasons"]}


# test-analyzer: disable=STG003 reason="4xx assertion without typed error body; tightened in #263"
def test_account_risk_summary_is_workspace_scoped() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        visible = create_account(session, external_ref="+15550102003")
        visible.account_state = AccountState.EXECUTION_USABLE
        visible.runtime_state.session_present = True
        visible.runtime_state.runtime_health = "ready"

        hidden_workspace = _seed_second_workspace(session)
        hidden = create_account(
            session, external_ref="+15550102004", workspace_id=hidden_workspace.id
        )
        hidden.account_state = AccountState.REAUTH_REQUIRED
        hidden.runtime_state.reauth_required = True
        hidden.runtime_state.runtime_health = "closed"
        session.commit()
        hidden_id = hidden.id

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="local-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="owner",
        auth_source="test",
    )
    client = TestClient(app)
    try:
        summary = client.get("/api/accounts/risk-summary")
        hidden_detail = client.get(f"/api/accounts/{hidden_id}/risk")
    finally:
        app.dependency_overrides.clear()

    assert summary.status_code == 200
    payload = summary.json()
    assert payload["total"] == 1
    assert payload["low"] == 1
    assert payload["critical"] == 0
    assert len(payload["items"]) == 1
    assert hidden_detail.status_code == 404


@freeze_time("2026-01-15 12:00:00")
def test_account_risk_includes_proxy_and_cooldown_reasons() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = create_account(session, external_ref="+15550102005")
        account.account_state = AccountState.EXECUTION_USABLE
        account.runtime_state.session_present = True
        account.runtime_state.runtime_health = "ready"
        account.proxy = AccountProxy(
            proxy_type="http",
            host="proxy.local",
            port=8080,
            status="failed",
            tdlib_last_error_code="TDLIB_PROXY_FAILED",
        )
        session.add(
            AccountOperationCooldown(
                account_id=account.id,
                operation="profile_update",
                level="blocked",
                reason_code="recent_flood_wait",
                started_at=datetime.now(UTC),
                retry_after_at=datetime.now(UTC) + timedelta(minutes=10),
                source="test",
            )
        )
        session.commit()
        account_id = account.id

    override_app_session(session_factory)
    try:
        response = TestClient(app).get(f"/api/accounts/{account_id}/risk")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    codes = {reason["code"] for reason in response.json()["reasons"]}
    assert "proxy_problem" in codes
    assert "cooldown_active" in codes
    assert response.json()["score"] <= 100


def _seed_second_workspace(session) -> Workspace:
    user = User(
        email="second@example.test",
        external_auth_provider="test",
        external_auth_user_id="second-user",
    )
    workspace = Workspace(name="Second", slug="second", owner=user)
    member = WorkspaceMember(workspace=workspace, user=user, role="owner")
    session.add_all([user, workspace, member])
    session.flush()
    session.add(WorkspacePlan(workspace_id=workspace.id))
    session.commit()
    session.refresh(workspace)
    return workspace
