from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import WorkspaceSafetyPolicyRead, WorkspaceSafetyPolicyUpdate
from app.services.auth_context import AuthContext, require_role
from app.services.sensitive_audit import record_sensitive_audit_event
from app.services.workspace_safety_policy import (
    get_workspace_safety_policy,
    update_workspace_safety_policy,
)

router = APIRouter(prefix="/api/safety-policy", tags=["safety-policy"])


@router.get("", response_model=WorkspaceSafetyPolicyRead)
def get_safety_policy(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_role("admin")),
):
    policy = get_workspace_safety_policy(
        session,
        workspace_id=auth.workspace_id,
        create_if_missing=True,
    )
    session.commit()
    return policy


@router.patch("", response_model=WorkspaceSafetyPolicyRead)
def patch_safety_policy(
    payload: WorkspaceSafetyPolicyUpdate,
    request: Request,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_role("admin")),
):
    previous = get_workspace_safety_policy(
        session,
        workspace_id=auth.workspace_id,
        create_if_missing=True,
    )
    previous_mode = previous.mode if previous is not None else None
    values = payload.model_dump(exclude_unset=True)
    policy = update_workspace_safety_policy(
        session,
        workspace_id=auth.workspace_id,
        values=values,
    )
    record_sensitive_audit_event(
        session,
        workspace_id=auth.workspace_id,
        actor_user_id=auth.user_id,
        action="workspace_safety_policy.updated",
        entity_type="workspace_safety_policy",
        entity_id=policy.id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={
            "previous_mode": previous_mode,
            "new_mode": policy.mode,
            "updated_fields": sorted(values),
        },
    )
    session.commit()
    return policy
