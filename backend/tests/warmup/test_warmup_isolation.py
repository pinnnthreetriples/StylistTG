"""Tests for the warmup isolation claim service.

Контрактный тест: сторонний модуль, вызывающий `ensure_not_isolated`
на аккаунте, захваченном warmup-сессией, получает чистый `AppError(409)`.
"""

from __future__ import annotations

import pytest

from app.errors import AppError
from app.models import (
    Account,
    AccountState,
    DEFAULT_LOCAL_USER_ID,
    DEFAULT_LOCAL_WORKSPACE_ID,
    User,
    UserStatus,
    Workspace,
    new_id,
)
from app.services.warmup_isolation import (
    ISOLATION_ERROR_CODE,
    acquire_claim,
    ensure_not_isolated,
    get_claim,
    list_claims_for_workspace,
    release_claim,
)


def _seed_account(db_session) -> str:
    user = db_session.get(User, DEFAULT_LOCAL_USER_ID)
    if user is None:
        user = User(
            id=DEFAULT_LOCAL_USER_ID,
            email="local@example.com",
            display_name="Local",
            external_auth_provider="local",
            external_auth_user_id=DEFAULT_LOCAL_USER_ID,
            status=UserStatus.ACTIVE,
        )
        db_session.add(user)
    workspace = db_session.get(Workspace, DEFAULT_LOCAL_WORKSPACE_ID)
    if workspace is None:
        workspace = Workspace(
            id=DEFAULT_LOCAL_WORKSPACE_ID,
            name="Local",
            slug="local",
            owner_user_id=DEFAULT_LOCAL_USER_ID,
        )
        db_session.add(workspace)
    account = Account(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        external_ref=f"+7999{new_id()[:8]}",
        account_state=AccountState.EXECUTION_USABLE,
    )
    db_session.add(account)
    db_session.commit()
    return account.id


def test_acquire_claim_is_idempotent_for_same_owner(db_session) -> None:
    account_id = _seed_account(db_session)

    first = acquire_claim(
        db_session,
        account_id=account_id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        held_by="warmup:session-1",
        reason="warmup_in_progress",
    )
    second = acquire_claim(
        db_session,
        account_id=account_id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        held_by="warmup:session-1",
        reason="warmup_in_progress",
    )

    assert first is True
    assert second is True
    snapshot = get_claim(db_session, account_id=account_id)
    assert snapshot is not None
    assert snapshot.held_by == "warmup:session-1"


def test_acquire_claim_rejected_for_different_owner(db_session) -> None:
    account_id = _seed_account(db_session)
    acquire_claim(
        db_session,
        account_id=account_id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        held_by="warmup:session-1",
        reason="warmup_in_progress",
    )

    acquired_by_other = acquire_claim(
        db_session,
        account_id=account_id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        held_by="campaigns:flow-9",
        reason="campaign_launch",
    )

    assert acquired_by_other is False
    snapshot = get_claim(db_session, account_id=account_id)
    assert snapshot is not None
    assert snapshot.held_by == "warmup:session-1"


def test_release_claim_only_by_owner(db_session) -> None:
    account_id = _seed_account(db_session)
    acquire_claim(
        db_session,
        account_id=account_id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        held_by="warmup:session-1",
        reason="warmup_in_progress",
    )

    released_by_other = release_claim(
        db_session, account_id=account_id, held_by="warmup:session-OTHER"
    )
    assert released_by_other is False
    assert get_claim(db_session, account_id=account_id) is not None

    released_by_owner = release_claim(db_session, account_id=account_id, held_by="warmup:session-1")
    assert released_by_owner is True
    assert get_claim(db_session, account_id=account_id) is None


# test-analyzer: disable=STG003 reason="asserts on AppError attributes (status_code + error_code + details), not a response body — already strict" permanent="true"
def test_ensure_not_isolated_raises_409_when_claim_held(db_session) -> None:
    account_id = _seed_account(db_session)
    acquire_claim(
        db_session,
        account_id=account_id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        held_by="warmup:session-1",
        reason="warmup_in_progress",
    )

    with pytest.raises(AppError) as excinfo:
        ensure_not_isolated(db_session, account_id=account_id)

    assert excinfo.value.status_code == 409
    assert excinfo.value.error_code == ISOLATION_ERROR_CODE
    assert excinfo.value.details["held_by"] == "warmup:session-1"


def test_ensure_not_isolated_is_noop_without_claim(db_session) -> None:
    account_id = _seed_account(db_session)
    # Should not raise — returns None when no claim exists.
    result = ensure_not_isolated(db_session, account_id=account_id)
    assert result is None


def test_list_claims_for_workspace_returns_snapshots(db_session) -> None:
    account_id_a = _seed_account(db_session)
    account_id_b = _seed_account(db_session)
    acquire_claim(
        db_session,
        account_id=account_id_a,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        held_by="warmup:a",
        reason="warmup_in_progress",
    )
    acquire_claim(
        db_session,
        account_id=account_id_b,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        held_by="warmup:b",
        reason="warmup_in_progress",
    )

    claims = list_claims_for_workspace(db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID)
    owners = {claim.held_by for claim in claims}
    assert {"warmup:a", "warmup:b"}.issubset(owners)
