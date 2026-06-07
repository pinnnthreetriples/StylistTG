from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import ACTIVE_WARMUP_STATUSES, Account, Job, JobState, WarmupSession
from app.modules.account_lifecycle.transitions import AccountLifecycleState

ACTIVE_JOB_STATES = (
    JobState.QUEUED.value,
    JobState.RUNNING.value,
    JobState.WAITING_LOCK.value,
)


def detect_idle_accounts(
    session: Session,
    workspace_id: str,
    *,
    threshold_minutes: int = 60,
    now: datetime,
) -> list[str]:
    cutoff = now - timedelta(minutes=threshold_minutes)
    active_jobs = (
        select(Job.id)
        .where(Job.workspace_id == workspace_id)
        .where(Job.workspace_id == Account.workspace_id)
        .where(Job.account_id == Account.id)
        .where(Job.job_state.in_(ACTIVE_JOB_STATES))
        .exists()
    )
    recent_jobs = (
        select(Job.id)
        .where(Job.workspace_id == workspace_id)
        .where(Job.workspace_id == Account.workspace_id)
        .where(Job.account_id == Account.id)
        .where(
            or_(
                Job.finished_at >= cutoff,
                Job.started_at >= cutoff,
                Job.queued_at >= cutoff,
            )
        )
        .exists()
    )
    active_warmup = (
        select(WarmupSession.id)
        .where(WarmupSession.workspace_id == workspace_id)
        .where(WarmupSession.workspace_id == Account.workspace_id)
        .where(WarmupSession.account_id == Account.id)
        .where(WarmupSession.status.in_([state.value for state in ACTIVE_WARMUP_STATUSES]))
        .exists()
    )
    accounts = session.execute(
        select(Account)
        .where(Account.workspace_id == workspace_id)
        .where(Account.lifecycle_state == AccountLifecycleState.ACTIVE.value)
        .where(~active_jobs)
        .where(~recent_jobs)
        .where(~active_warmup)
        .order_by(Account.updated_at.asc(), Account.id.asc())
    ).scalars()
    return [account.id for account in accounts]


def list_idle_candidate_workspaces(session: Session) -> list[str]:
    return list(
        session.execute(
            select(  # nosemgrep: missing-workspace-id-filter-projection - scheduler fan-out intentionally enumerates active workspaces.
                Account.workspace_id
            )
            .where(Account.lifecycle_state == AccountLifecycleState.ACTIVE.value)
            .distinct()
            .order_by(Account.workspace_id.asc())
        ).scalars()
    )


__all__ = ["detect_idle_accounts", "list_idle_candidate_workspaces"]
