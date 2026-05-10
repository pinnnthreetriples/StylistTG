from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models import AccountRuntimeState, Job, JobState, StepStatus, utc_now

STALE_JOB_STATES = {JobState.QUEUED, JobState.RUNNING, JobState.WAITING_LOCK}


def reap_stale_jobs(session: Session, *, stale_after_seconds: int) -> int:
    cutoff = utc_now() - timedelta(seconds=stale_after_seconds)
    jobs = list(
        session.execute(
            select(Job)
            .where(
                or_(
                    and_(Job.job_state == JobState.QUEUED, Job.queued_at.is_not(None), Job.queued_at < cutoff),
                    and_(Job.job_state == JobState.RUNNING, Job.started_at.is_not(None), Job.started_at < cutoff),
                    and_(Job.job_state == JobState.WAITING_LOCK, Job.queued_at.is_not(None), Job.queued_at < cutoff),
                )
            )
        ).scalars()
    )
    for job in jobs:
        for step in job.step_results:
            if step.status == StepStatus.STARTED:
                step.status = StepStatus.UNCERTAIN
                step.uncertain_reason = "worker_timeout"
                step.finished_at = utc_now()
        job.job_state = JobState.FAILED
        job.finished_at = utc_now()
        job.failure_reason = "worker_timeout"
        runtime = session.get(AccountRuntimeState, job.account_id)
        if runtime and (runtime.updated_at is None or _is_before(runtime.updated_at, cutoff)):
            runtime.lock_owner = None
            runtime.recovery_marker = "stale_job_reaped"
            runtime.updated_at = utc_now()
    session.commit()
    return len(jobs)


def reconcile_orphaned_queued_jobs(
    session: Session,
    *,
    min_age_seconds: int = 60,
    is_enqueued: Callable[[str], bool] | None = None,
) -> int:
    cutoff = utc_now() - timedelta(seconds=min_age_seconds)
    jobs = list(
        session.execute(
            select(Job)
            .where(Job.job_state == JobState.QUEUED)
            .where(Job.queued_at.is_not(None))
            .where(Job.queued_at < cutoff)
        ).scalars()
    )
    if not jobs:
        return 0
    reconciled = 0
    for job in jobs:
        if is_enqueued is not None and is_enqueued(job.id):
            continue
        if not _try_reenqueue_or_fail(job):
            job.job_state = JobState.FAILED
            job.finished_at = utc_now()
            job.failure_reason = "queue_lost"
        reconciled += 1
    session.commit()
    return reconciled


def _try_reenqueue_or_fail(job: Job) -> bool:
    try:
        from app.job_queue.rq import reenqueue_job_with_delay

        return reenqueue_job_with_delay(
            job.id,
            delay_seconds=0,
            workflow_type=job.workflow_type,
        )
    except Exception:
        return False


def _is_before(value: datetime, cutoff: datetime) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=UTC)
    return value < cutoff
