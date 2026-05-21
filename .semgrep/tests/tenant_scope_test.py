from sqlalchemy import select

from app.models import Account, Workspace


def positive_missing_workspace_filter(account_id: str):
    # ruleid: missing-workspace-id-filter
    return select(Account).where(Account.id == account_id)


def positive_missing_workspace_filter_non_id_lookup(external_ref: str):
    # ruleid: missing-workspace-id-filter
    return select(Account).where(Account.external_ref == external_ref)


def negative_with_workspace_filter(account_id: str, workspace_id: str):
    # ok: missing-workspace-id-filter
    return select(Account).where(
        Account.id == account_id, Account.workspace_id == workspace_id
    )


def positive_projection_missing_workspace_filter(account_id: str):
    # ruleid: missing-workspace-id-filter-projection
    return select(Account.id).where(Account.id == account_id)


def negative_projection_with_workspace_filter(account_id: str, workspace_id: str):
    # ok: missing-workspace-id-filter-projection
    return select(Account.id).where(
        Account.id == account_id, Account.workspace_id == workspace_id
    )


def negative_workspace_model(workspace_id: str):
    # ok: missing-workspace-id-filter
    return select(Workspace).where(Workspace.id == workspace_id)
