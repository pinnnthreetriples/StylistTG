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
from app.services.account_quarantine import create_quarantine
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


def _open_test_quarantine(db_session, account, source_attempt_id: str):
    quarantine = handle_flood_wait(
        db_session,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        flood_wait_seconds=120,
        source_attempt_id=source_attempt_id,
    )
    db_session.commit()
    return quarantine


def _create_manual_quarantine(db_session, account, *, duration_hours: int, metadata=None):
    return create_quarantine(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        reason="manual",
        duration_hours=duration_hours,
        metadata=metadata,
    )


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


def test_create_quarantine_is_idempotent_for_unreleased_account(db_session) -> None:
    account = seed_account(db_session)

    first = _create_manual_quarantine(db_session, account, duration_hours=4)
    second = _create_manual_quarantine(db_session, account, duration_hours=4)

    rows = db_session.query(AccountQuarantine).filter_by(account_id=account.id).all()
    assert second.id == first.id
    assert len(rows) == 1


def test_create_quarantine_extends_existing_until_for_longer_duplicate(db_session) -> None:
    account = seed_account(db_session)
    first = _create_manual_quarantine(db_session, account, duration_hours=1)
    original_until = first.until

    second = _create_manual_quarantine(db_session, account, duration_hours=8)

    assert second.id == first.id
    assert second.until > original_until


def test_create_quarantine_does_not_shorten_existing_until(db_session) -> None:
    account = seed_account(db_session)
    first = _create_manual_quarantine(db_session, account, duration_hours=8)
    original_until = first.until

    second = _create_manual_quarantine(db_session, account, duration_hours=1)

    assert second.id == first.id
    assert second.until == original_until


def test_create_quarantine_merges_metadata_for_duplicate(db_session) -> None:
    account = seed_account(db_session)
    first = _create_manual_quarantine(
        db_session, account, duration_hours=4, metadata={"first": "kept"}
    )

    second = _create_manual_quarantine(
        db_session, account, duration_hours=4, metadata={"second": "added"}
    )

    assert second.id == first.id
    assert second.metadata_json == {"first": "kept", "second": "added"}


def test_released_quarantine_allows_new_row(db_session) -> None:
    account = seed_account(db_session)
    first = _create_manual_quarantine(db_session, account, duration_hours=4)
    first.released_at = utc_now()
    db_session.flush()

    second = _create_manual_quarantine(db_session, account, duration_hours=4)

    assert second.id != first.id
    assert db_session.query(AccountQuarantine).filter_by(account_id=account.id).count() == 2


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


def test_admin_override_release_releases_unexpired_quarantine_and_audits(
    admin_client, db_session
) -> None:
    account = seed_account(db_session)
    quarantine = handle_flood_wait(
        db_session,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        flood_wait_seconds=120,
        source_attempt_id="attempt-admin-1",
    )
    quarantine.until = utc_now() + timedelta(hours=6)
    db_session.commit()

    response = admin_client.post(
        f"/api/accounts/{account.id}/quarantine/admin-override",
        json={"reason": "mistaken flood wait release"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == quarantine.id
    assert payload["released_at"] is not None
    assert payload["released_by_user_id"] == DEFAULT_LOCAL_USER_ID
    assert payload["metadata_json"]["admin_override_release_reason"] == (
        "mistaken flood wait release"
    )

    db_session.refresh(quarantine)
    assert quarantine.released_at is not None
    assert quarantine.metadata_json["admin_override_release_reason"] == (
        "mistaken flood wait release"
    )

    event = db_session.query(SensitiveAuditEvent).one()
    assert event.action == "quarantine.admin_override_released"
    assert event.account_id == account.id
    assert event.reason == "mistaken flood wait release"
    assert event.metadata_json["before"]["id"] == quarantine.id
    assert event.metadata_json["after"]["released_by_user_id"] == DEFAULT_LOCAL_USER_ID


def test_admin_override_release_expired_quarantine_returns_404(admin_client, db_session) -> None:
    account = seed_account(db_session)
    quarantine = handle_flood_wait(
        db_session,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        flood_wait_seconds=120,
        source_attempt_id="attempt-admin-expired",
    )
    quarantine.until = utc_now() - timedelta(minutes=5)
    db_session.commit()

    response = admin_client.post(
        f"/api/accounts/{account.id}/quarantine/admin-override",
        json={"reason": "mistaken flood wait release"},
    )

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body or "error_code" in body


def test_admin_override_release_no_active_quarantine_returns_404(admin_client, db_session) -> None:
    account = seed_account(db_session)

    response = admin_client.post(
        f"/api/accounts/{account.id}/quarantine/admin-override",
        json={"reason": "mistaken flood wait release"},
    )

    assert response.status_code == 404
    body = response.json()
    assert "message" in body or "detail" in body


def test_admin_override_release_non_admin_returns_403(app_client, db_session) -> None:
    app.dependency_overrides[get_current_auth_context] = lambda: _auth("operator")
    account = seed_account(db_session)
    _open_test_quarantine(db_session, account, "attempt-admin-2")

    response = app_client.post(
        f"/api/accounts/{account.id}/quarantine/admin-override",
        json={"reason": "mistaken flood wait release"},
    )

    assert response.status_code == 403
    body = response.json()
    assert "detail" in body or "error_code" in body


def test_admin_override_release_short_reason_returns_422(admin_client, db_session) -> None:
    account = seed_account(db_session)
    _open_test_quarantine(db_session, account, "attempt-admin-3")

    response = admin_client.post(
        f"/api/accounts/{account.id}/quarantine/admin-override",
        json={"reason": "too short"},
    )

    assert response.status_code == 422
    body = response.json()
    assert "error_code" in body or "detail" in body
    assert body["field_errors"]


def test_admin_override_release_cross_tenant_returns_404(app_client, db_session) -> None:
    workspace_a, workspace_b = seed_two_workspaces(db_session)
    app.dependency_overrides[get_current_auth_context] = lambda: _auth(
        "admin", workspace_id=workspace_a
    )
    account_b = seed_account(
        db_session,
        external_ref="+15550108888",
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

    response = app_client.post(
        f"/api/accounts/{account_b.id}/quarantine/admin-override",
        json={"reason": "mistaken flood wait release"},
    )

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body or "error_code" in body


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
