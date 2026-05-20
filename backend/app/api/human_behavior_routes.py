from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.contracts.human_behavior import BehaviorProfileRead
from app.db import get_session
from app.services.auth_context import AuthContext, require_role
from app.services.human_behavior.behavior_profile import get_or_create_baseline

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("/{account_id}/behavior-profile", response_model=BehaviorProfileRead)
def get_behavior_profile(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_role("admin")),
):
    require_account_in_workspace(session, account_id, auth)
    profile = get_or_create_baseline(
        session,
        account_id=account_id,
        workspace_id=auth.workspace_id,
    )
    session.commit()
    return profile
