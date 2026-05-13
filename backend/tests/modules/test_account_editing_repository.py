from __future__ import annotations

import pytest

from app.modules.account_editing.repository import AccountEditingRepository
from tests.helpers.factories import seed_account_with_profile, seed_two_workspaces


def test_repository_loads_account_by_workspace(db_session) -> None:
    account = seed_account_with_profile(db_session, external_ref="+15550104001")
    repo = AccountEditingRepository(db_session)

    loaded = repo.get_account(account_id=account.id, workspace_id=account.workspace_id)

    assert loaded is not None
    assert loaded.id == account.id


def test_repository_does_not_return_foreign_workspace_account(db_session) -> None:
    _, foreign_workspace_id = seed_two_workspaces(db_session)
    account = seed_account_with_profile(
        db_session,
        external_ref="+15550104002",
        workspace_id=foreign_workspace_id,
    )
    repo = AccountEditingRepository(db_session)

    assert repo.get_account(account_id=account.id, workspace_id="local") is None


def test_repository_require_account_preserves_missing_account_error(db_session) -> None:
    repo = AccountEditingRepository(db_session)

    with pytest.raises(ValueError, match="^account not found$"):
        repo.require_account(account_id="missing", workspace_id="local")
