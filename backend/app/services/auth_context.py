from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.errors import AppError
from app.models import UserStatus, WorkspaceRole, WorkspaceStatus
from app.services.supabase_jwt import SupabaseJwtVerifier
from app.services.workspace_onboarding import resolve_workspace_membership
from app.services.workspaces import ensure_default_workspace


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    workspace_id: str
    role: str
    auth_source: str
    is_system: bool = False


ROLE_ORDER = {"viewer": 0, "operator": 1, "admin": 2, "owner": 3}


def get_current_auth_context(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> AuthContext:
    if settings.auth_mode == "local":
        user, workspace, member = ensure_default_workspace(session)
        session.commit()
        return AuthContext(
            user_id=user.id,
            workspace_id=workspace.id,
            role=member.role,
            auth_source="local",
        )
    if settings.auth_mode == "supabase_jwt":
        token = _bearer_token(request)
        claims = SupabaseJwtVerifier.from_settings(settings).verify(token)
        provider_user_id = str(claims["sub"])
        email = str(claims.get("email") or "")
        from app.services.users import get_or_create_external_user

        user = get_or_create_external_user(
            session,
            provider="supabase",
            external_user_id=provider_user_id,
            email=email,
            display_name=claims.get("name"),
        )
        member = resolve_workspace_membership(
            session,
            user=user,
            requested_workspace_id=request.headers.get("X-Workspace-Id"),
        )
        if member is None:
            raise AppError(
                status_code=status.HTTP_403_FORBIDDEN,
                error_code="WORKSPACE_ACCESS_DENIED",
                error_class="forbidden",
                message="workspace access denied",
            )
        _ensure_active_membership(user.status, member.workspace.status, member.role)
        session.commit()
        return AuthContext(
            user_id=user.id,
            workspace_id=member.workspace_id,
            role=member.role,
            auth_source="supabase_jwt",
        )
    raise AppError(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="AUTH_MODE_UNSUPPORTED",
        error_class="configuration",
        message="auth mode is unsupported",
    )


def require_authenticated(
    context: Annotated[AuthContext, Depends(get_current_auth_context)],
) -> AuthContext:
    return context


def require_role(*roles: str):
    minimum = max(ROLE_ORDER[role] for role in roles)

    def dependency(context: Annotated[AuthContext, Depends(require_authenticated)]) -> AuthContext:
        if ROLE_ORDER.get(context.role, -1) < minimum:
            raise AppError(
                status_code=status.HTTP_403_FORBIDDEN,
                error_code="ROLE_FORBIDDEN",
                error_class="forbidden",
                message="insufficient workspace role",
            )
        return context

    return dependency


def require_mutation_permission(
    context: Annotated[AuthContext, Depends(require_role("operator"))],
) -> AuthContext:
    return context


def _bearer_token(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise AppError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTH_REQUIRED",
            error_class="auth_required",
            message="authorization bearer token is required",
        )
    return authorization[len(prefix) :].strip()


def _ensure_active_membership(user_status: str, workspace_status: str, role: str) -> None:
    if user_status != UserStatus.ACTIVE:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="USER_DISABLED",
            error_class="forbidden",
            message="user is disabled",
        )
    if workspace_status != WorkspaceStatus.ACTIVE:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="WORKSPACE_DISABLED",
            error_class="forbidden",
            message="workspace is disabled",
        )
    if role not in {item.value for item in WorkspaceRole}:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="ROLE_INVALID",
            error_class="forbidden",
            message="workspace role is invalid",
        )
