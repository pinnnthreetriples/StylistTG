from __future__ import annotations

from datetime import UTC, datetime, timedelta

from freezegun import freeze_time

from app.models import AccountSafetyOverride, new_id
from app.services.account_safety_overrides import (
    active_overrides_by_operation,
    batch_active_overrides_by_operation,
    create_safety_override,
)
from app.services.accounts import create_account
from tests.helpers.factories import seed_two_workspaces


def test_create_safety_override_persists_workspace_id(db_session) -> None:
    account = create_account(db_session, external_ref="+15550106000")
    db_session.commit()

    payload = create_safety_override(
        db_session,
        account.id,
        workspace_id=account.workspace_id,
        operation="profile_update",
        reason="operator accepted warning",
        requested_blockers=["fresh_validity_required"],
    )

    row = db_session.query(AccountSafetyOverride).one()
    assert row.workspace_id == account.workspace_id
    assert payload["id"] == row.id


@freeze_time("2026-05-26 12:00:00")
def test_active_overrides_missing_matching_workspace_returns_empty(db_session) -> None:
    home_ws, foreign_ws = seed_two_workspaces(db_session)
    account = create_account(
        db_session,
        external_ref="+15550106001",
        workspace_id=home_ws,
    )
    db_session.add(
        AccountSafetyOverride(
            id=new_id(),
            workspace_id=foreign_ws,
            account_id=account.id,
            operation="profile_update",
            reason="forged wrong workspace",
            requested_blockers_json=["fresh_validity_required"],
            allowed_until=datetime.now(UTC) + timedelta(minutes=30),
        )
    )
    db_session.commit()

    overrides = active_overrides_by_operation(
        db_session,
        account.id,
        workspace_id=home_ws,
    )

    assert overrides == {}


@freeze_time("2026-05-26 12:00:00")
def test_batch_active_overrides_missing_matching_workspace_returns_empty(db_session) -> None:
    home_ws, foreign_ws = seed_two_workspaces(db_session)
    account = create_account(
        db_session,
        external_ref="+15550106002",
        workspace_id=home_ws,
    )
    db_session.add(
        AccountSafetyOverride(
            id=new_id(),
            workspace_id=foreign_ws,
            account_id=account.id,
            operation="profile_music",
            reason="forged wrong workspace",
            requested_blockers_json=["music_capability_not_checked"],
            allowed_until=datetime.now(UTC) + timedelta(minutes=30),
        )
    )
    db_session.commit()

    overrides = batch_active_overrides_by_operation(
        db_session,
        [account.id],
        workspace_id=home_ws,
    )

    assert overrides == {}
