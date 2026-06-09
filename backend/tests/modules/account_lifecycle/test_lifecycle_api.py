from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import DEFAULT_LOCAL_USER_ID, DEFAULT_LOCAL_WORKSPACE_ID
from app.modules.account_lifecycle.interfaces import AccountLifecycleState, advance
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated
from app.services.accounts import create_account

NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


def test_get_account_lifecycle_returns_state_and_transition_history(
    db_session: Session,
    app_client: TestClient,
) -> None:
    account = create_account(db_session, external_ref="+15553740001")
    advance(
        db_session,
        account,
        to_state=AccountLifecycleState.COLD_SOAK,
        now=NOW,
        reason="api_test_started",
        actor_user_id=DEFAULT_LOCAL_USER_ID,
    )
    db_session.commit()
    app.dependency_overrides[require_authenticated] = lambda: AuthContext(
        user_id=DEFAULT_LOCAL_USER_ID,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="viewer",
        auth_source="test",
    )

    response = app_client.get(f"/api/accounts/{account.id}/lifecycle")

    assert response.status_code == 200
    payload = response.json()
    assert payload["account_id"] == account.id
    assert payload["lifecycle_state"] == AccountLifecycleState.COLD_SOAK.value
    assert payload["history"][0]["from_state"] == AccountLifecycleState.IMPORTED.value
    assert payload["history"][0]["to_state"] == AccountLifecycleState.COLD_SOAK.value
    assert payload["history"][0]["reason"] == "api_test_started"


def test_get_account_lifecycle_is_workspace_scoped(
    db_session: Session,
    app_client: TestClient,
) -> None:
    account = create_account(db_session, external_ref="+15553740002")
    app.dependency_overrides[require_authenticated] = lambda: AuthContext(
        user_id=DEFAULT_LOCAL_USER_ID,
        workspace_id="00000000-0000-4000-8000-000000000099",
        role="viewer",
        auth_source="test",
    )

    response = app_client.get(f"/api/accounts/{account.id}/lifecycle")

    assert response.status_code == 404
    assert response.json().get("error_code")
