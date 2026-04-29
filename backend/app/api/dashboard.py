from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.account_context import account_id_header
from app.db import get_session
from app.errors import AppError
from app.schemas import DashboardProfileRead
from app.services.dashboard import build_dashboard_profile

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/profile/{account_id}", response_model=DashboardProfileRead)
def get_dashboard_profile(account_id: str, session: Session = Depends(get_session)):
    return _dashboard_profile_response(account_id, session)


@router.get("/profile", response_model=DashboardProfileRead)
def get_dashboard_profile_from_header(
    account_id: str = Depends(account_id_header),
    session: Session = Depends(get_session),
):
    return _dashboard_profile_response(account_id, session)


def _dashboard_profile_response(account_id: str, session: Session) -> DashboardProfileRead:
    try:
        payload = build_dashboard_profile(session, account_id)
    except ValueError as exc:
        raise AppError(
            status_code=404,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message=str(exc),
        ) from exc
    return DashboardProfileRead(**payload)
