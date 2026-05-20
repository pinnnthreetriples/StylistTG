from __future__ import annotations

from datetime import UTC, datetime, timedelta

from freezegun import freeze_time
from sqlalchemy import select

from app.main import app
from app.models import (
    DEFAULT_LOCAL_USER_ID,
    DEFAULT_LOCAL_WORKSPACE_ID,
    Account,
    AccountQuarantine,
    BoughtOnboardingState,
    SensitiveAuditEvent,
    utc_now,
)
from app.services.auth_context import AuthContext, get_current_auth_context
from app.services.bought_account_onboarding import process_rest_period_ggr_check
from tests.helpers.factories import seed_account, seed_two_workspaces

_FROZEN_NOW = datetime(2026, 5, 20, 14, 37, 0, tzinfo=UTC)


def _auth(role: str = "admin", workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID) -> AuthContext:
    return AuthContext(
        user_id=DEFAULT_LOCAL_USER_ID,
        workspace_id=workspace_id,
        role=role,
        auth_source="test",
    )


def _admin_override(workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID) -> None:
    app.dependency_overrides[get_current_auth_context] = lambda: _auth("admin", workspace_id)


def _scheduled_noop(*args, **kwargs) -> bool:
    return True


def _seed_started_onboarding(db_session, *, external_ref: str) -> tuple[Account, AccountQuarantine]:
    account = seed_account(db_session, external_ref=external_ref, origin="bought")
    state = BoughtOnboardingState(account_id=account.id, workspace_id=account.workspace_id)
    quarantine = AccountQuarantine(
        workspace_id=account.workspace_id,
        account_id=account.id,
        reason="bought_rest_period",
        started_at=_FROZEN_NOW,
        until=_FROZEN_NOW + timedelta(days=5),
        metadata_json={},
    )
    db_session.add_all([state, quarantine])
    return account, quarantine


def test_account_origin_defaults_to_imported_for_existing_style_rows(db_session) -> None:
    account = Account(external_ref="+15550108888")

    db_session.add(account)
    db_session.flush()

    assert account.origin == "imported"


@freeze_time(_FROZEN_NOW)
def test_bought_account_start_creates_rest_quarantine_and_audit(
    app_client, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.services.bought_account_onboarding.schedule_bought_onboarding_action",
        _scheduled_noop,
    )
    _admin_override()
    account = seed_account(db_session, external_ref="+15550108000", origin="bought")

    response = app_client.post(f"/api/accounts/{account.id}/bought-onboarding/start")

    assert response.status_code == 201
    payload = response.json()
    assert payload["current_step"] == "enable_2fa"
    assert payload["completion_percent"] == 25
    quarantine = db_session.query(AccountQuarantine).one()
    assert quarantine.reason == "bought_rest_period"
    assert quarantine.until.replace(tzinfo=UTC) == _FROZEN_NOW + timedelta(hours=120)
    assert db_session.query(SensitiveAuditEvent).one().action == "bought_onboarding.started"


@freeze_time(_FROZEN_NOW + timedelta(days=5))
def test_rest_period_ggr_weak_extends_quarantine(db_session, monkeypatch) -> None:
    account, quarantine = _seed_started_onboarding(db_session, external_ref="+15550108001")
    monkeypatch.setattr(
        "app.services.bought_account_onboarding._calculate_ggr_bucket", lambda *a: "weak"
    )

    result = process_rest_period_ggr_check(
        db_session, account_id=account.id, workspace_id=account.workspace_id
    )

    assert result.current_step == "ggr_precheck"
    assert result.details_json["ggr_bucket"] == "weak"
    assert quarantine.until == utc_now() + timedelta(hours=72)
    assert quarantine.released_at is None


@freeze_time(_FROZEN_NOW + timedelta(days=5))
def test_rest_period_ggr_strong_releases_quarantine(db_session, monkeypatch) -> None:
    account, quarantine = _seed_started_onboarding(db_session, external_ref="+15550108002")
    monkeypatch.setattr(
        "app.services.bought_account_onboarding._calculate_ggr_bucket", lambda *a: "strong"
    )

    result = process_rest_period_ggr_check(
        db_session, account_id=account.id, workspace_id=account.workspace_id
    )

    assert result.current_step == "completed"
    assert result.completed_at == utc_now()
    assert quarantine.released_at == utc_now()
    assert quarantine.released_by_user_id == DEFAULT_LOCAL_USER_ID


@freeze_time(_FROZEN_NOW)
def test_start_is_tenant_scoped(app_client, db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.bought_account_onboarding.schedule_bought_onboarding_action",
        _scheduled_noop,
    )
    workspace_a, workspace_b = seed_two_workspaces(db_session)
    _admin_override(workspace_a)
    account_b = seed_account(
        db_session,
        external_ref="+15550108003",
        workspace_id=workspace_b,
        origin="bought",
    )

    response = app_client.post(f"/api/accounts/{account_b.id}/bought-onboarding/start")

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body or "error_code" in body
    assert db_session.execute(select(BoughtOnboardingState)).scalars().all() == []
