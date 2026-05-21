from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.errors import AppError
from app.models import Workspace
from app.schemas import WorkspaceFeatureFlagsUpdate, WorkspaceRead
from app.services.auth_context import AuthContext, require_role
from app.services.sensitive_audit import record_sensitive_audit_event

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.patch("/{workspace_id}/feature-flags", response_model=WorkspaceRead)
def patch_workspace_feature_flags(
    workspace_id: str,
    payload: WorkspaceFeatureFlagsUpdate,
    request: Request,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_role("admin")),
):
    workspace = _workspace_for_auth(session, workspace_id=workspace_id, auth=auth)
    workspace.safety_pipeline_v2_enabled = payload.safety_pipeline_v2_enabled
    record_sensitive_audit_event(
        session,
        workspace_id=auth.workspace_id,
        actor_user_id=auth.user_id,
        action="workspace.feature_flag.updated",
        entity_type="workspace",
        entity_id=workspace.id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={
            "flag": "safety_pipeline_v2_enabled",
            "new_value": payload.safety_pipeline_v2_enabled,
        },
    )
    session.commit()
    session.refresh(workspace)
    return workspace


def _workspace_for_auth(
    session: Session,
    *,
    workspace_id: str,
    auth: AuthContext,
) -> Workspace:
    workspace = session.get(Workspace, workspace_id) if workspace_id == auth.workspace_id else None
    if workspace is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="WORKSPACE_NOT_FOUND",
            error_class="not_found",
            message="workspace not found",
        )
    return workspace
