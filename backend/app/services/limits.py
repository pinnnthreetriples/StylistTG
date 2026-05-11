from __future__ import annotations

from datetime import UTC, datetime, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, Job, UsageCounter, WorkspacePlan, utc_now


class WorkspaceLimitError(ValueError):
    pass


def require_billing_active(session: Session, workspace_id: str) -> None:
    plan = _plan(session, workspace_id)
    if plan.billing_status != "active":
        raise WorkspaceLimitError("billing required")


def check_workspace_limit(
    session: Session, workspace_id: str, metric: str, requested: int = 1
) -> None:
    require_billing_active(session, workspace_id)
    plan = _plan(session, workspace_id)
    if metric == "accounts":
        current = (
            session.scalar(
                select(func.count(Account.id)).where(Account.workspace_id == workspace_id)
            )
            or 0
        )
        limit = plan.max_accounts
    elif metric == "batch_size":
        current = 0
        limit = plan.max_batch_size
    elif metric == "jobs_per_day":
        current = _jobs_created_today(session, workspace_id)
        limit = plan.max_jobs_per_day
    else:
        return
    if current + requested > limit:
        raise WorkspaceLimitError(f"{metric} limit exceeded")


def increment_usage(
    session: Session, workspace_id: str, metric: str, value: int = 1
) -> UsageCounter:
    start = datetime.combine(utc_now().date(), time.min, tzinfo=UTC)
    end = datetime.combine(utc_now().date(), time.max, tzinfo=UTC)
    counter = (
        session.query(UsageCounter)
        .filter_by(workspace_id=workspace_id, period_start=start, period_end=end, metric=metric)
        .one_or_none()
    )
    if counter is None:
        counter = UsageCounter(
            workspace_id=workspace_id, period_start=start, period_end=end, metric=metric, value=0
        )
        session.add(counter)
    counter.value += value
    session.flush()
    return counter


def _plan(session: Session, workspace_id: str) -> WorkspacePlan:
    plan = session.get(WorkspacePlan, workspace_id)
    if plan is None:
        raise WorkspaceLimitError("workspace plan is not configured")
    return plan


def _jobs_created_today(session: Session, workspace_id: str) -> int:
    start = datetime.combine(utc_now().date(), time.min, tzinfo=UTC)
    return (
        session.scalar(
            select(func.count(Job.id)).where(
                Job.workspace_id == workspace_id, Job.queued_at >= start
            )
        )
        or 0
    )
