from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.account_context import account_id_header
from app.api.tenant_helpers import require_account_in_workspace
from app.db import get_session
from app.schemas import (
    AccountRuntimeDiagnosticsRead,
    AuthStateRead,
    JobSummaryRead,
    RuntimeRefreshRead,
)
from app.services.auth_context import (
    AuthContext,
    require_authenticated,
    require_mutation_permission,
)

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("/auth-state", response_model=AuthStateRead)
def get_account_auth_state_from_header(
    account_id: str = Depends(account_id_header),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    from app.api.auth import _auth_response
    from app.services.auth import get_auth_state

    return _auth_response(get_auth_state(session, account_id))


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
    from app.api.account_jobs_routes import list_jobs

    return list_jobs(account_id, limit, session, auth)


@router.get("/jobs/latest", response_model=JobSummaryRead)
def latest_job_from_header(
    account_id: str = Depends(account_id_header),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    from app.api.account_jobs_routes import latest_job

    return latest_job(account_id, session, auth)
