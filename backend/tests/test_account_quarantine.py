from __future__ import annotations

from datetime import timedelta

import pytest

from app.main import app
from app.models import (
    DEFAULT_LOCAL_USER_ID,
    DEFAULT_LOCAL_WORKSPACE_ID,
    SensitiveAuditEvent,
    AccountQuarantine,
    WorkspaceSafetyPolicy,
    new_id,
    utc_now,
)
from app.services.account_quarantine import handle_flood_wait, is_account_quarantined
from app.services.auth_context import AuthContext, get_current_auth_context
from app.services.workspaces import ensure_default_workspace
from tests.helpers.factories import seed_account, seed_two_workspaces


def _auth(role: str = "admin", workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID) -> AuthContext:
    return AuthContext(
        user_id=DEFAULT_LOCAL_USER_ID,
        workspace_id=workspace_id,
        role=role,
        auth_source="test",
    )


@pytest.fixture()
def admin_client(app_client):
    app.dependency_overrides[get_current_auth_context] = lambda: _auth("admin")
    return app_client


def test_handle_flood_wait_creates_default_24h_quarantine(db_session) -> None:
    account = seed_account(db_session)

    quarantine = handle_flood_wait(
        db_session,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        flood_wait_seconds=180,
        source_attempt_id="attempt-1",
    )

    delta = quarantine.until - quarantine.started_at
    assert 23.9 * 3600 <= delta.total_seconds() <= 24.1 * 3600
    assert quarantine.reason == "flood_wait"
    assert quarantine.metadata_json == {
        "original_flood_wait_seconds": 180,
        "source_attempt_id": "attempt-1",
    }


def test_handle_flood_wait_reads_policy_quarantine_hours(db_session) -> None:
    ensure_default_workspace(db_session)
    db_session.add(
        WorkspaceSafetyPolicy(
            id=new_id(),
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            quarantine_hours_on_flood_wait=6,
        )
    )
    account = seed_account(db_session)

    quarantine = handle_flood_wait(
        db_session,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        flood_wait_seconds=60,
        source_attempt_id="attempt-2",
    )

    delta = quarantine.until - quarantine.started_at
    assert 5.9 * 3600 <= delta.total_seconds() <= 6.1 * 3600


def test_is_account_quarantined_active_then_false_after_expiry(db_session) -> None:
    account = seed_account(db_session)
    quarantine = handle_flood_wait(
        db_session,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        flood_wait_seconds=60,
        source_attempt_id="attempt-3",
    )
    db_session.commit()

    assert (
        is_account_quarantined(
            db_session,
            account_id=account.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        )
        is True
    )

    quarantine.until = utc_now() - timedelta(seconds=1)
    db_session.commit()

    assert (
        is_account_quarantined(
            db_session,
            account_id=account.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        )
        is False
    )


def test_get_endpoint_returns_active_quarantine(admin_client, db_session) -> None:
    account = seed_account(db_session)
    quarantine = handle_flood_wait(
        db_session,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        flood_wait_seconds=120,
        source_attempt_id="attempt-4",
    )
    db_session.commit()

    response = admin_client.get(f"/api/accounts/{account.id}/quarantine")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == quarantine.id
    assert payload["account_id"] == account.id
    assert payload["reason"] == "flood_wait"


def test_release_endpoint_sets_release_fields_and_audit(admin_client, db_session) -> None:
    account = seed_account(db_session)
    quarantine = handle_flood_wait(
        db_session,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        flood_wait_seconds=120,
        source_attempt_id="attempt-5",
    )
    db_session.commit()

    response = admin_client.post(
        f"/api/accounts/{account.id}/quarantine/release",
        json={"reason": "manual recovery"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == quarantine.id
    assert payload["released_at"] is not None
    assert payload["released_by_user_id"] == DEFAULT_LOCAL_USER_ID

    db_session.refresh(quarantine)
    assert quarantine.released_at is not None
    assert quarantine.released_by_user_id == DEFAULT_LOCAL_USER_ID

    event = db_session.query(SensitiveAuditEvent).one()
    assert event.action == "account_quarantine.released"
    assert event.account_id == account.id
    assert event.metadata_json["before"]["id"] == quarantine.id
    assert event.metadata_json["after"]["released_by_user_id"] == DEFAULT_LOCAL_USER_ID


def test_release_endpoint_non_admin_returns_403(app_client, db_session) -> None:
    app.dependency_overrides[get_current_auth_context] = lambda: _auth("operator")
    account = seed_account(db_session)
    handle_flood_wait(
        db_session,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        flood_wait_seconds=120,
        source_attempt_id="attempt-6",
    )
    db_session.commit()

    response = app_client.post(
        f"/api/accounts/{account.id}/quarantine/release",
        json={"reason": "not allowed"},
    )

    assert response.status_code == 403
    body = response.json()
    assert "detail" in body or "error_code" in body


def test_tenant_isolation_workspace_a_cannot_see_workspace_b_quarantine(
    app_client, db_session
) -> None:
    workspace_a, workspace_b = seed_two_workspaces(db_session)
    app.dependency_overrides[get_current_auth_context] = lambda: _auth(
        "admin", workspace_id=workspace_a
    )
    account_b = seed_account(
        db_session,
        external_ref="+15550109999",
        workspace_id=workspace_b,
    )
    db_session.add(
        AccountQuarantine(
            id=new_id(),
            workspace_id=workspace_b,
            account_id=account_b.id,
            reason="manual",
            started_at=utc_now(),
            until=utc_now() + timedelta(hours=24),
            metadata_json={},
        )
    )
    db_session.commit()

    response = app_client.get(f"/api/accounts/{account_b.id}/quarantine")

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body or "error_code" in body
