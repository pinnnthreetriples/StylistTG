from __future__ import annotations

from app.job_queue import workflows


ACCOUNT_UPDATE_WORKFLOW_TYPE = "account_update"


def enqueue_account_update_job(job_id: str) -> bool:
    return workflows.enqueue_workflow(
        workflow_type=ACCOUNT_UPDATE_WORKFLOW_TYPE,
        job_id=job_id,
    )


def reenqueue_account_update_job_with_delay(job_id: str, *, delay_seconds: int) -> bool:
    return workflows.reenqueue_workflow_with_delay(
        workflow_type=ACCOUNT_UPDATE_WORKFLOW_TYPE,
        job_id=job_id,
        delay_seconds=delay_seconds,
    )


__all__ = [
    "ACCOUNT_UPDATE_WORKFLOW_TYPE",
    "enqueue_account_update_job",
    "reenqueue_account_update_job_with_delay",
]
