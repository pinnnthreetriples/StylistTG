from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.db import get_session
from app.modules.account_core.context import account_id_header as _account_id_header
from app.modules.account_jobs.interfaces import latest_job_summary, list_job_summaries
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import (
    require_authenticated,
    require_mutation_permission,
)
from app.schemas import (
    AccountRuntimeDiagnosticsRead,
    AuthStateRead,
    JobSummaryRead,
    RuntimeRefreshRead,
)

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def account_id_header(x_account_id: str = Header(alias="X-Account-Id")) -> str:
    return _account_id_header(x_account_id)


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
    return list_job_summaries(session, account_id, limit=limit, workspace_id=auth.workspace_id)


@router.get("/jobs/latest", response_model=JobSummaryRead)
def latest_job_from_header(
    account_id: str = Depends(account_id_header),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    return latest_job_summary(session, account_id, workspace_id=auth.workspace_id)


__all__ = ["router"]
