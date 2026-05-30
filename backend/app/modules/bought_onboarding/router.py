from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.db import get_session
from app.errors import AppError
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated, require_role
from app.modules.bought_onboarding.contracts import BoughtOnboardingStatusRead
from app.modules.bought_onboarding.service import (
    get_onboarding_state,
    start_bought_onboarding,
    status_read,
)
from app.services.sensitive_audit import record_sensitive_audit_event

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.post(
    "/{account_id}/bought-onboarding/start",
    response_model=BoughtOnboardingStatusRead,
    status_code=status.HTTP_201_CREATED,
)
def start_account_bought_onboarding(
    account_id: str,
    request: Request,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_role("admin")),
) -> BoughtOnboardingStatusRead:
    account = require_account_in_workspace(session, account_id, auth)
    if account.origin != "bought":
        raise AppError(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="ACCOUNT_ORIGIN_NOT_BOUGHT",
            error_class="validation",
            message="bought onboarding can start only for bought accounts",
        )

    state = start_bought_onboarding(session, account=account, workspace_id=auth.workspace_id)
    record_sensitive_audit_event(
        session,
        workspace_id=auth.workspace_id,
        actor_user_id=auth.user_id,
        action="bought_onboarding.started",
        entity_type="account",
        entity_id=account.id,
        account_id=account.id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"current_step": state.current_step, "origin": account.origin},
    )
    session.commit()
    session.refresh(state)
    return status_read(state)


@router.get(
    "/{account_id}/bought-onboarding/status",
    response_model=BoughtOnboardingStatusRead,
)
def get_account_bought_onboarding_status(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> BoughtOnboardingStatusRead:
    require_account_in_workspace(session, account_id, auth)
    state = get_onboarding_state(session, account_id=account_id, workspace_id=auth.workspace_id)
    if state is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="BOUGHT_ONBOARDING_NOT_FOUND",
            error_class="not_found",
            message="bought onboarding state not found",
        )
    return status_read(state)


__all__ = ["router"]
