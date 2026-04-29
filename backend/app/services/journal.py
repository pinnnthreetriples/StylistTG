from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, JobState, JobStepResult, StepStatus, utc_now
from app.services.locks import fenced_write_allowed


def mark_job_running(
    session: Session, job: Job, *, owner: str, lock_epoch: int
) -> bool:
    if not fenced_write_allowed(session, job.account_id, owner, lock_epoch):
        return False
    job.job_state = JobState.RUNNING
    job.started_at = utc_now()
    session.commit()
    return True


def record_step_started(session: Session, job: Job, event: dict) -> JobStepResult:
    plan_step = _plan_step(job, event["step_key"])
    step = JobStepResult(
        job_id=job.id,
        step_key=event["step_key"],
        step_type=event["step_type"],
        status=StepStatus.STARTED,
        step_order=plan_step.get("order") if plan_step else None,
        capability_key=plan_step.get("capability_key") if plan_step else None,
        attempt_no=1,
        started_at=utc_now(),
    )
    session.add(step)
    session.commit()
    session.refresh(step)
    return step


def _latest_step(session: Session, job_id: str, step_key: str) -> JobStepResult | None:
    statement = (
        select(JobStepResult)
        .where(JobStepResult.job_id == job_id)
        .where(JobStepResult.step_key == step_key)
        .order_by(JobStepResult.started_at.desc())
    )
    return session.execute(statement).scalars().first()


def _plan_step(job: Job, step_key: str) -> dict | None:
    for step in job.plan_json_snapshot.get("steps", []):
        if step.get("step_key") == step_key:
            return step
    return None


def record_step_succeeded(session: Session, job: Job, event: dict) -> None:
    step = _latest_step(session, job.id, event["step_key"])
    if step is None:
        step = record_step_started(session, job, event)
    step.status = StepStatus.SUCCEEDED
    step.finished_at = utc_now()
    step.verification_attempted = event.get("verification_attempted", False)
    step.verification_result = event.get("verification_result")
    step.result_payload_json = event.get("result_payload")
    session.commit()


def record_step_failed(session: Session, job: Job, event: dict) -> None:
    step = _latest_step(session, job.id, event["step_key"])
    if step is None:
        step = record_step_started(session, job, event)
    step.status = StepStatus.FAILED
    step.finished_at = utc_now()
    step.error_code = event.get("error_code")
    step.error_class = event.get("error_class")
    step.result_payload_json = event.get("result_payload")
    session.commit()


def record_step_uncertain(session: Session, job: Job, event: dict) -> None:
    step = _latest_step(session, job.id, event["step_key"])
    if step is None:
        step = record_step_started(session, job, event)
    step.status = StepStatus.UNCERTAIN
    step.finished_at = utc_now()
    step.verification_attempted = event.get("verification_attempted", False)
    step.verification_result = event.get("verification_result")
    step.uncertain_reason = event.get("uncertain_reason")
    step.result_payload_json = event.get("result_payload")
    session.commit()


def mark_started_steps_uncertain(session: Session, job: Job, reason: str) -> None:
    for step in job.step_results:
        if step.status == StepStatus.STARTED:
            step.status = StepStatus.UNCERTAIN
            step.uncertain_reason = reason
            step.finished_at = utc_now()
    session.commit()


def mark_terminal(
    session: Session,
    job: Job,
    *,
    state: JobState,
    owner: str,
    lock_epoch: int,
    failure_reason: str | None = None,
) -> bool:
    if not fenced_write_allowed(session, job.account_id, owner, lock_epoch):
        return False
    job.job_state = state
    job.finished_at = utc_now()
    job.failure_reason = failure_reason
    session.commit()
    return True
