from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, JobState, StepStatus
from app.services.journal import mark_started_steps_uncertain


def recover_interrupted_jobs(session: Session) -> list[Job]:
    statement = select(Job).where(Job.job_state.in_([JobState.RUNNING, JobState.WAITING_LOCK]))
    recovered: list[Job] = []
    for job in session.execute(statement).scalars().all():
        has_started_step = any(step.status == StepStatus.STARTED for step in job.step_results)
        if has_started_step:
            mark_started_steps_uncertain(session, job, "worker_or_child_interrupted")
            job.job_state = JobState.MANUAL_INTERVENTION_NEEDED
            job.failure_reason = "recovered_uncertain_step"
        else:
            job.job_state = JobState.FAILED
            job.failure_reason = "recovered_without_started_step"
        recovered.append(job)
    session.commit()
    return recovered
