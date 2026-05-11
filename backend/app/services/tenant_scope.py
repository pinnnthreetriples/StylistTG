from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountOperationLog, AccountProxy, Asset, AuthBatch, Job


def get_account_for_workspace(
    session: Session, account_id: str, workspace_id: str
) -> Account | None:
    return (
        session.execute(
            select(Account).where(Account.id == account_id, Account.workspace_id == workspace_id)
        )
        .scalars()
        .first()
    )


def get_job_for_workspace(session: Session, job_id: str, workspace_id: str) -> Job | None:
    return (
        session.execute(select(Job).where(Job.id == job_id, Job.workspace_id == workspace_id))
        .scalars()
        .first()
    )


def get_asset_for_workspace(session: Session, asset_id: str, workspace_id: str) -> Asset | None:
    return (
        session.execute(
            select(Asset).where(Asset.id == asset_id, Asset.workspace_id == workspace_id)
        )
        .scalars()
        .first()
    )


def get_auth_batch_for_workspace(
    session: Session, batch_id: str, workspace_id: str
) -> AuthBatch | None:
    return (
        session.execute(
            select(AuthBatch).where(
                AuthBatch.id == batch_id, AuthBatch.workspace_id == workspace_id
            )
        )
        .scalars()
        .first()
    )


def get_proxy_account_for_workspace(
    session: Session, account_id: str, workspace_id: str
) -> AccountProxy | None:
    account = get_account_for_workspace(session, account_id, workspace_id)
    if account is None:
        return None
    return session.get(AccountProxy, account_id)


def get_operation_log_for_workspace(
    session: Session, log_id: str, workspace_id: str
) -> AccountOperationLog | None:
    return (
        session.execute(
            select(AccountOperationLog).where(
                AccountOperationLog.id == log_id,
                AccountOperationLog.workspace_id == workspace_id,
            )
        )
        .scalars()
        .first()
    )


def assert_account_workspace(session: Session, account_id: str, workspace_id: str) -> Account:
    account = get_account_for_workspace(session, account_id, workspace_id)
    if account is None:
        raise ValueError("account not found")
    return account


def assert_job_account_workspace_consistency(job: Job) -> None:
    account = cast(Any, job.account)
    if account is None or account.workspace_id != job.workspace_id:
        raise ValueError("workspace_account_mismatch")
