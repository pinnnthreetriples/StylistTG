from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time

from app.main import app
from app.models import (
    DEFAULT_LOCAL_USER_ID,
    DEFAULT_LOCAL_WORKSPACE_ID,
    Account,
    AccountQuarantine,
)
from app.services.auth_context import AuthContext, get_current_auth_context
from app.services.disaster_state import evaluate_disaster_state
from app.services.workspaces import ensure_default_workspace
from tests.helpers.factories import seed_account, seed_two_workspaces

_FROZEN_NOW = datetime(2026, 5, 22, 12, 0, tzinfo=UTC)


@pytest.fixture()
def dashboard_client(app_client) -> Iterator:
    try:
        app.dependency_overrides[get_current_auth_context] = lambda: _auth()
        yield app_client
    finally:
        app.dependency_overrides.clear()


def _auth(workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID) -> AuthContext:
    return AuthContext(
        user_id=DEFAULT_LOCAL_USER_ID,
        workspace_id=workspace_id,
        role="admin",
        auth_source="test",
    )


def _seed_accounts(db_session, count: int, *, workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID):
    return [
        seed_account(db_session, external_ref=f"+15550102{index:03d}", workspace_id=workspace_id)
        for index in range(count)
    ]


def _seed_quarantines(
    db_session,
    accounts: list[Account],
    *,
    started_at: datetime = _FROZEN_NOW - timedelta(minutes=10),
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
) -> None:
    db_session.add_all(
        AccountQuarantine(
            workspace_id=workspace_id,
            account_id=account.id,
            reason="manual",
            started_at=started_at,
            until=_FROZEN_NOW + timedelta(hours=1),
            metadata_json={},
        )
        for account in accounts
    )
    db_session.commit()


@freeze_time(_FROZEN_NOW)
def test_empty_workspace_is_not_disaster(db_session) -> None:
    ensure_default_workspace(db_session)

    state = evaluate_disaster_state(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        now=_FROZEN_NOW,
    )

    assert state.is_disaster is False
    assert state.quarantined_fraction == 0.0
    assert state.total_accounts == 0


@freeze_time(_FROZEN_NOW)
def test_zero_quarantined_accounts_is_not_disaster(db_session) -> None:
    _seed_accounts(db_session, 10)

    state = evaluate_disaster_state(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        now=_FROZEN_NOW,
    )

    assert state.is_disaster is False
    assert state.quarantined_count == 0
    assert state.quarantined_fraction == 0.0


@freeze_time(_FROZEN_NOW)
def test_exact_threshold_is_not_disaster(db_session) -> None:
    accounts = _seed_accounts(db_session, 10)
    _seed_quarantines(db_session, accounts[:5])

    state = evaluate_disaster_state(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        now=_FROZEN_NOW,
    )

    assert state.is_disaster is False
    assert state.quarantined_count == 5
    assert state.quarantined_fraction == 0.5


@freeze_time(_FROZEN_NOW)
def test_above_threshold_is_disaster(db_session) -> None:
    accounts = _seed_accounts(db_session, 10)
    _seed_quarantines(db_session, accounts[:6])

    state = evaluate_disaster_state(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        now=_FROZEN_NOW,
    )

    assert state.is_disaster is True
    assert state.quarantined_count == 6
    assert len(state.sample_quarantined_account_ids) == 5


@freeze_time(_FROZEN_NOW)
def test_old_quarantines_outside_window_are_not_disaster(db_session) -> None:
    accounts = _seed_accounts(db_session, 10)
    _seed_quarantines(db_session, accounts[:6], started_at=_FROZEN_NOW - timedelta(hours=2))

    state = evaluate_disaster_state(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        now=_FROZEN_NOW,
    )

    assert state.is_disaster is False
    assert state.quarantined_count == 0
    assert state.quarantined_fraction == 0.0


@freeze_time(_FROZEN_NOW)
def test_api_uses_authenticated_workspace_state(dashboard_client, db_session) -> None:
    workspace_a, workspace_b = seed_two_workspaces(db_session)
    accounts_a = _seed_accounts(db_session, 10, workspace_id=workspace_a)
    accounts_b = _seed_accounts(db_session, 10, workspace_id=workspace_b)
    _seed_quarantines(db_session, accounts_a[:6], workspace_id=workspace_a)
    _seed_quarantines(db_session, accounts_b[:2], workspace_id=workspace_b)

    response = dashboard_client.get("/api/dashboard/disaster-state")
    payload = response.json()

    assert response.status_code == 200
    assert payload["workspace_id"] == workspace_a
    assert payload["is_disaster"] is True
    assert payload["quarantined_count"] == 6
