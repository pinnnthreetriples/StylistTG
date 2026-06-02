from __future__ import annotations

import pytest
from sqlalchemy import text

from app.main import app
from app.models import (
    DEFAULT_LOCAL_USER_ID,
    DEFAULT_LOCAL_WORKSPACE_ID,
    SensitiveAuditEvent,
)
from app.services.auth_context import AuthContext, get_current_auth_context
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


def _set_terminal_status(db_session, account_id: str, status: str) -> None:
    db_session.execute(
        text("UPDATE account SET terminal_status = :status WHERE id = :account_id"),
        {"status": status, "account_id": account_id},
    )
    db_session.commit()


def _terminal_status(db_session, account_id: str) -> str:
    return str(
        db_session.execute(
            text("SELECT terminal_status FROM account WHERE id = :account_id"),
            {"account_id": account_id},
        ).scalar_one()
    )


def test_clear_terminal_status_banned_to_none_and_audits(admin_client, db_session) -> None:
    account = seed_account(db_session)
    _set_terminal_status(db_session, account.id, "banned")

    response = admin_client.post(
        f"/api/accounts/{account.id}/terminal-status/clear",
        json={"reason": "mistaken ban classification"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "account_id": account.id,
        "previous_terminal_status": "banned",
        "terminal_status": "none",
    }
    assert _terminal_status(db_session, account.id) == "none"

    event = db_session.query(SensitiveAuditEvent).one()
    assert event.action == "account.terminal_status_cleared"
    assert event.account_id == account.id
    assert event.reason == "mistaken ban classification"
    assert event.metadata_json["previous_terminal_status"] == "banned"
    assert event.metadata_json["terminal_status"] == "none"


def test_clear_terminal_status_none_returns_409(admin_client, db_session) -> None:
    account = seed_account(db_session)

    response = admin_client.post(
        f"/api/accounts/{account.id}/terminal-status/clear",
        json={"reason": "mistaken ban classification"},
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error_code"] == "TERMINAL_STATUS_ALREADY_NONE"


def test_clear_terminal_status_non_admin_returns_403(app_client, db_session) -> None:
    app.dependency_overrides[get_current_auth_context] = lambda: _auth("operator")
    account = seed_account(db_session)
    _set_terminal_status(db_session, account.id, "banned")

    response = app_client.post(
        f"/api/accounts/{account.id}/terminal-status/clear",
        json={"reason": "mistaken ban classification"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error_code"] == "ROLE_FORBIDDEN"


# test-analyzer: disable=STG003 reason="STG003 false positive — body asserts field_errors length and the expected `reason` field name; rule does not yet recognise field_errors-based contract"
def test_clear_terminal_status_short_reason_returns_422(admin_client, db_session) -> None:
    account = seed_account(db_session)
    _set_terminal_status(db_session, account.id, "banned")

    response = admin_client.post(
        f"/api/accounts/{account.id}/terminal-status/clear",
        json={"reason": "too short"},
    )

    assert response.status_code == 422
    body = response.json()
    # field_errors must mention the offending reason field so the UI can render it.
    assert len(body["field_errors"]) >= 1
    field_names = {entry.get("field") for entry in body["field_errors"]}
    assert "reason" in field_names, (
        f"expected `reason` in field_errors, got {body['field_errors']!r}"
    )


def test_clear_terminal_status_cross_tenant_returns_404(app_client, db_session) -> None:
    workspace_a, workspace_b = seed_two_workspaces(db_session)
    app.dependency_overrides[get_current_auth_context] = lambda: _auth(
        "admin", workspace_id=workspace_a
    )
    account_b = seed_account(
        db_session,
        external_ref="+15550107777",
        workspace_id=workspace_b,
    )
    _set_terminal_status(db_session, account_b.id, "banned")

    response = app_client.post(
        f"/api/accounts/{account_b.id}/terminal-status/clear",
        json={"reason": "mistaken ban classification"},
    )

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body or "error_code" in body
