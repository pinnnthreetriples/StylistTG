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
        .where(
            Job.workspace_id == workspace_id,
            Job.workspace_id == Account.workspace_id,
            Job.account_id == Account.id,
            Job.job_state.in_(ACTIVE_JOB_STATES),
        )
        .exists()
    )
    recent_jobs = (
        select(Job.id)
        .where(
            Job.workspace_id == workspace_id,
            Job.workspace_id == Account.workspace_id,
            Job.account_id == Account.id,
            or_(
                Job.finished_at >= cutoff,
                Job.started_at >= cutoff,
                Job.queued_at >= cutoff,
            ),
        )
        .exists()
    )
    active_warmup = (
        select(WarmupSession.id)
        .where(
            WarmupSession.workspace_id == workspace_id,
            WarmupSession.workspace_id == Account.workspace_id,
            WarmupSession.account_id == Account.id,
            WarmupSession.status.in_([state.value for state in ACTIVE_WARMUP_STATUSES]),
        )
        .exists()
    )
    return list(
        session.execute(
            select(Account.id)
            .where(
                Account.workspace_id == workspace_id,
                Account.lifecycle_state == AccountLifecycleState.ACTIVE.value,
                ~active_jobs,
                ~recent_jobs,
                ~active_warmup,
            )
            .order_by(Account.updated_at.asc(), Account.id.asc())
        ).scalars()
    )


def list_idle_candidate_workspaces(session: Session) -> list[str]:
    # nosemgrep: stylisttg.missing-workspace-id-filter-projection
    return list(
        session.execute(
            select(Account.workspace_id)
            .where(Account.lifecycle_state == AccountLifecycleState.ACTIVE.value)
            .distinct()
            .order_by(Account.workspace_id.asc())
        ).scalars()
    )


__all__ = ["detect_idle_accounts", "list_idle_candidate_workspaces"]
