from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.db import get_session
from app.modules.account_jobs.interfaces import latest_job_summary, list_job_summaries
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated
from app.schemas import JobSummaryRead

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("/{account_id}/jobs", response_model=list[JobSummaryRead])
def list_jobs(
    account_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    return list_job_summaries(session, account_id, limit=limit, workspace_id=auth.workspace_id)


@router.get("/{account_id}/jobs/latest", response_model=JobSummaryRead)
def latest_job(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    return latest_job_summary(session, account_id, workspace_id=auth.workspace_id)


__all__ = ["router"]
