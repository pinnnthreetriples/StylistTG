from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import WorkspaceSafetyPolicyRead, WorkspaceSafetyPolicyUpdate
from app.modules.account_safety.policy import (
    compute_diff,
    get_workspace_safety_policy,
    is_workspace_safety_policy_temporarily_disabled,
    policy_public_snapshot,
    update_workspace_safety_policy,
)
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_role
from app.services.sensitive_audit import record_sensitive_audit_event

router = APIRouter(prefix="/api/safety-policy", tags=["safety-policy"])


def _serialize(policy: object) -> WorkspaceSafetyPolicyRead:
    read = WorkspaceSafetyPolicyRead.model_validate(policy)
    if is_workspace_safety_policy_temporarily_disabled():
        read = read.model_copy(update={"temporarily_disabled": True})
    return read


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
    return _serialize(policy)


@router.patch("", response_model=WorkspaceSafetyPolicyRead)
def patch_safety_policy(
    payload: WorkspaceSafetyPolicyUpdate,
    request: Request,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_role("admin")),
):
    if is_workspace_safety_policy_temporarily_disabled():
        # Kill-switch on: PATCH is a no-op. Return the neutral policy so the
        # client sees consistent state and no audit log entry is recorded.
        policy = get_workspace_safety_policy(
            session,
            workspace_id=auth.workspace_id,
            create_if_missing=True,
        )
        return _serialize(policy)
    previous = get_workspace_safety_policy(
        session,
        workspace_id=auth.workspace_id,
        create_if_missing=True,
    )
    previous_snapshot = policy_public_snapshot(previous) if previous is not None else {}
    values = payload.model_dump(exclude_unset=True)
    policy = update_workspace_safety_policy(
        session,
        workspace_id=auth.workspace_id,
        values=values,
    )
    diff = compute_diff(previous_snapshot, policy)
    if diff["changed_fields"]:
        record_sensitive_audit_event(
            session,
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
            action="workspace_safety_policy.updated",
            entity_type="workspace_safety_policy",
            entity_id=policy.id,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            metadata=diff,
        )
    session.commit()
    return _serialize(policy)
