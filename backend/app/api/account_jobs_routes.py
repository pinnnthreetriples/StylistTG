from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.db import get_session
from app.errors import AppError
from app.schemas import JobSummaryRead
from app.services.auth_context import AuthContext, require_authenticated
from app.services.dashboard import job_summary
from app.services.jobs import get_latest_account_job, list_account_jobs

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("/{account_id}/jobs", response_model=list[JobSummaryRead])
def list_jobs(
    account_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    return [
        JobSummaryRead(**job_summary(job))
        for job in list_account_jobs(session, account_id, limit=limit, workspace_id=auth.workspace_id)
    ]


@router.get("/{account_id}/jobs/latest", response_model=JobSummaryRead)
def latest_job(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    job = get_latest_account_job(session, account_id, workspace_id=auth.workspace_id)
    if job is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="JOB_NOT_FOUND",
            error_class="not_found",
            message="job not found",
        )
    return JobSummaryRead(**job_summary(job))
