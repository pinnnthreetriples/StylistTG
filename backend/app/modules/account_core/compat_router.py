from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.db import get_session
from app.errors import AppError
from app.modules.account_core.context import account_id_header
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated, require_mutation_permission
from app.schemas import (
    AccountRuntimeDiagnosticsRead,
    AuthStateRead,
    JobSummaryRead,
    RuntimeRefreshRead,
)
from app.services.dashboard import job_summary
from app.services.jobs import get_latest_account_job, list_account_jobs

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("/auth-state", response_model=AuthStateRead)
def get_account_auth_state_from_header(
    account_id: str = Depends(account_id_header),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    from app.api.auth import auth_response
    from app.services.auth import get_auth_state

    return auth_response(get_auth_state(session, account_id, workspace_id=auth.workspace_id))


@router.post("/refresh-runtime", response_model=RuntimeRefreshRead)
def refresh_runtime_from_header(
    account_id: str = Depends(account_id_header),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    from app.api.account_runtime_routes import refresh_runtime

    return refresh_runtime(account_id, session, auth)


@router.get("/runtime-diagnostics", response_model=AccountRuntimeDiagnosticsRead)
def runtime_diagnostics_from_header(
    account_id: str = Depends(account_id_header),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    from app.api.account_runtime_routes import runtime_diagnostics

    return runtime_diagnostics(account_id, session, auth)


@router.get("/jobs", response_model=list[JobSummaryRead])
def list_jobs_from_header(
    account_id: str = Depends(account_id_header),
    limit: int = Query(default=10, ge=1, le=100),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    return [
        JobSummaryRead(**job_summary(job))
        for job in list_account_jobs(
            session, account_id, limit=limit, workspace_id=auth.workspace_id
        )
    ]


@router.get("/jobs/latest", response_model=JobSummaryRead)
def latest_job_from_header(
    account_id: str = Depends(account_id_header),
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


__all__ = ["router"]
