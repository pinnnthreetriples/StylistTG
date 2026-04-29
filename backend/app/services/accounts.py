from sqlalchemy import delete, select
from sqlalchemy import not_
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Account, AccountAuthAttempt, AccountRuntimeState, AccountState, Job, TERMINAL_JOB_STATES
from app.services.stale_jobs import reap_stale_jobs


def create_account(
    session: Session,
    *,
    external_ref: str,
    telegram_user_id: str | None = None,
    auth_source: str = "otp",
) -> Account:
    account = Account(
        external_ref=external_ref,
        telegram_user_id=telegram_user_id,
        auth_source=auth_source,
        account_state=AccountState.REGISTERED,
    )
    account.runtime_state = AccountRuntimeState(
        session_present=False,
        runtime_health="unknown",
        reauth_required=False,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def get_account(session: Session, account_id: str) -> Account | None:
    return session.get(Account, account_id)


def get_account_by_external_ref(session: Session, external_ref: str) -> Account | None:
    return session.execute(
        select(Account).where(Account.external_ref == external_ref)
    ).scalars().first()


def list_accounts(session: Session) -> list[Account]:
    return list(
        session.execute(
            select(Account)
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
        .scalars()
        .all()
    )


def delete_account(session: Session, account_id: str) -> None:
    account = get_account(session, account_id)
    if account is None:
        raise ValueError("account not found")

    reap_stale_jobs(session, stale_after_seconds=settings.stale_job_timeout_seconds)

    active_job = session.execute(
        select(Job.id)
        .where(Job.account_id == account_id)
        .where(Job.job_state.not_in([state.value for state in TERMINAL_JOB_STATES]))
        .limit(1)
    ).scalars().first()
    if active_job is not None:
        raise ValueError("active job cannot be deleted")

    terminal_jobs = list(session.execute(select(Job).where(Job.account_id == account_id)).scalars().all())
    for job in terminal_jobs:
        session.delete(job)

    session.execute(delete(AccountAuthAttempt).where(AccountAuthAttempt.account_id == account_id))
    session.delete(account)
    session.commit()
