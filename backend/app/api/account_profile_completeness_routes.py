from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.contracts.profile_completeness import ProfileCompletenessReport
from app.db import get_session
from app.services.account_profile_completeness import (
    ProfileCompletenessAccountNotFound,
    evaluate,
)
from app.services.auth_context import AuthContext, require_authenticated

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get(
    "/{account_id}/profile-completeness",
    response_model=ProfileCompletenessReport,
)
def get_account_profile_completeness(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> ProfileCompletenessReport:
    require_account_in_workspace(session, account_id, auth)
    try:
        return evaluate(session, workspace_id=auth.workspace_id, account_id=account_id)
    except ProfileCompletenessAccountNotFound as exc:
        raise HTTPException(status_code=404, detail="account not found") from exc
