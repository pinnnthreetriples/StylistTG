from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.errors import AppError
from app.models import User, Workspace, WorkspaceMember
from app.schemas import CurrentUserRead
from app.services.auth_context import AuthContext, require_authenticated

router = APIRouter(prefix="/api", tags=["me"])


@router.get("/me", response_model=CurrentUserRead)
def get_me(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> CurrentUserRead:
    user = session.get(User, auth.user_id)
    workspace = session.get(Workspace, auth.workspace_id)
    member = (
        session.query(WorkspaceMember)
        .filter_by(user_id=auth.user_id, workspace_id=auth.workspace_id)
        .one_or_none()
    )
    if user is None or workspace is None or member is None:
        raise AppError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="AUTH_CONTEXT_INVALID",
            error_class="configuration",
            message="auth context references missing user or workspace",
        )
    return CurrentUserRead(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        workspace_id=workspace.id,
        workspace_name=workspace.name,
        role=member.role,
        auth_source=auth.auth_source,
    )
