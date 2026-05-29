from __future__ import annotations

from sqlalchemy.orm import Session

from app.errors import AppError
from app.schemas import JobSummaryRead
from app.services.dashboard import job_summary
from app.services.jobs import get_latest_account_job, list_account_jobs


def list_job_summaries(
    session: Session, account_id: str, *, limit: int, workspace_id: str
) -> list[JobSummaryRead]:
    return [
        JobSummaryRead(**job_summary(job))
        for job in list_account_jobs(session, account_id, limit=limit, workspace_id=workspace_id)
    ]


def latest_job_summary(session: Session, account_id: str, *, workspace_id: str) -> JobSummaryRead:
    job = get_latest_account_job(session, account_id, workspace_id=workspace_id)
    if job is None:
        raise AppError(
            status_code=404,
            error_code="JOB_NOT_FOUND",
            error_class="not_found",
            message="job not found",
        )
    return JobSummaryRead(**job_summary(job))


__all__ = ["latest_job_summary", "list_job_summaries"]
