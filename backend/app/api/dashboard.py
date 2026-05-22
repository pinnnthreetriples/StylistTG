from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.account_context import account_id_header
from app.contracts.disaster_state import DisasterState
from app.db import get_session
from app.errors import AppError
from app.models import utc_now
from app.schemas import DashboardProfileRead
from app.services.auth_context import AuthContext, require_authenticated
from app.services.dashboard import build_dashboard_profile
from app.services.disaster_state import evaluate_disaster_state

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/disaster-state", response_model=DisasterState)
def get_disaster_state(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> DisasterState:
    return evaluate_disaster_state(session, workspace_id=auth.workspace_id, now=utc_now())


@router.get("/profile/{account_id}", response_model=DashboardProfileRead)
def get_dashboard_profile(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    return _dashboard_profile_response(account_id, session, auth.workspace_id)


@router.get("/profile", response_model=DashboardProfileRead)
def get_dashboard_profile_from_header(
    account_id: str = Depends(account_id_header),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    return _dashboard_profile_response(account_id, session, auth.workspace_id)


def _dashboard_profile_response(
    account_id: str, session: Session, workspace_id: str
) -> DashboardProfileRead:
    try:
        payload = build_dashboard_profile(session, account_id, workspace_id=workspace_id)
    except ValueError as exc:
        raise AppError(
            status_code=404,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message=str(exc),
        ) from exc
    return DashboardProfileRead(**payload)
