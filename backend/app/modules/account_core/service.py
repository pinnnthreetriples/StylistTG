from __future__ import annotations

from sqlalchemy import delete, not_, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    Account,
    AccountAuthAttempt,
    AccountRuntimeState,
    AccountState,
    Job,
    TERMINAL_JOB_STATES,
)
from app.services.audit_logs import log_audit_event
from app.services.limits import check_workspace_limit
from app.services.stale_jobs import reap_stale_jobs
from app.workspace_bootstrap import ensure_default_workspace


def create_account(
    session: Session,
    *,
    external_ref: str,
    telegram_user_id: str | None = None,
    auth_source: str = "otp",
    origin: str = "imported",
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    actor_user_id: str | None = None,
) -> Account:
    if origin not in {"imported", "bought", "created"}:
        raise ValueError("unsupported account origin")
    if workspace_id == DEFAULT_LOCAL_WORKSPACE_ID:
        ensure_default_workspace(session)
    check_workspace_limit(session, workspace_id, "accounts")
    if get_account_by_external_ref(session, external_ref, workspace_id=workspace_id) is not None:
        raise ValueError("account already exists")
    account = Account(
        workspace_id=workspace_id,
        external_ref=external_ref,
        telegram_user_id=telegram_user_id,
        auth_source=auth_source,
        origin=origin,
        account_state=AccountState.REGISTERED,
    )
    account.runtime_state = AccountRuntimeState(
        session_present=False,
        runtime_health="unknown",
        reauth_required=False,
    )
    session.add(account)
    log_audit_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="account.created",
        entity_type="account",
        entity_id=account.id,
        metadata={"auth_source": auth_source, "origin": origin},
    )
    session.commit()
    session.refresh(account)
    return account


def get_account(
    session: Session, account_id: str, workspace_id: str | None = None
) -> Account | None:
    if workspace_id is None:
        return session.get(Account, account_id)
    return (
        session.execute(
            select(Account).where(Account.id == account_id, Account.workspace_id == workspace_id)
        )
        .scalars()
        .first()
    )


def get_account_by_external_ref(
    session: Session,
    external_ref: str,
    *,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
) -> Account | None:
    return (
        session.execute(
            select(Account).where(
                Account.external_ref == external_ref, Account.workspace_id == workspace_id
            )
        )
        .scalars()
        .first()
    )


def list_accounts(
    session: Session, workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID
) -> list[Account]:
    return list(
        session.execute(
            select(Account)
            .options(
                joinedload(Account.profile_state),
                joinedload(Account.runtime_state),
                joinedload(Account.proxy),
            )
            .where(Account.workspace_id == workspace_id)
            .where(
                not_(
                    (Account.auth_source == "batch")
                    & Account.account_state.in_(
                        [
                            AccountState.REGISTERED,
                            AccountState.AUTH_PENDING,
                            AccountState.AWAITING_CODE,
                            AccountState.AWAITING_PASSWORD,
                        ]
                    )
                )
            )
            .order_by(Account.updated_at.desc())
        )
        .unique()
        .scalars()
        .all()
    )


def delete_account(
    session: Session,
    account_id: str,
    *,
    workspace_id: str | None = None,
    actor_user_id: str | None = None,
) -> None:
    account = get_account(session, account_id, workspace_id=workspace_id)
    if account is None:
        raise ValueError("account not found")

    reap_stale_jobs(session, stale_after_seconds=settings.stale_job_timeout_seconds)
    target_workspace_id = account.workspace_id

    active_job = (
        session.execute(
            select(Job)
            .where(
                Job.account_id == account_id,
                Job.workspace_id == target_workspace_id,
                Job.job_state.not_in([state.value for state in TERMINAL_JOB_STATES]),
            )
            .limit(1)
        )
        .scalars()
        .first()
    )
    if active_job is not None:
        raise ValueError("active job cannot be deleted")

    terminal_jobs = list(
        session.execute(
            select(Job).where(Job.account_id == account_id, Job.workspace_id == target_workspace_id)
        )
        .scalars()
        .all()
    )
    for job in terminal_jobs:
        session.delete(job)

    session.execute(delete(AccountAuthAttempt).where(AccountAuthAttempt.account_id == account_id))
    log_audit_event(
        session,
        workspace_id=account.workspace_id,
        actor_user_id=actor_user_id,
        action="account.deleted",
        entity_type="account",
        entity_id=account.id,
    )
    session.delete(account)
    session.commit()
