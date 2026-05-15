from __future__ import annotations

from typing import cast

from sqlalchemy.orm import Session

from app.config import settings
from app.modules.auth import repository
from app.modules.auth.context import AuthContext
from app.modules.auth.contracts import AuthRequestLike
from app.modules.auth.errors import auth_mode_unsupported, auth_required, workspace_access_denied
from app.modules.auth.policies import ensure_active_membership
from app.services.supabase_jwt import SupabaseJwtVerifier


def resolve_auth_context(request: AuthRequestLike, session: Session) -> AuthContext:
    if settings.auth_mode == "local":
        user, _workspace, member = repository.ensure_default_workspace(session)
        session.commit()
        return AuthContext(
            user_id=user.id,
            workspace_id=member.workspace_id,
            role=member.role,
            auth_source="local",
        )
    if settings.auth_mode == "supabase_jwt":
        token = _bearer_token(request)
        claims = SupabaseJwtVerifier.from_settings(settings).verify(token)
        provider_user_id = str(claims["sub"])
        email = str(claims.get("email") or "")
        user = repository.get_or_create_external_user(
            session,
            provider="supabase",
            external_user_id=provider_user_id,
            email=email,
            display_name=cast(str | None, claims.get("name")),
        )
        member = repository.resolve_workspace_membership(
            session,
            user=user,
            requested_workspace_id=request.headers.get("X-Workspace-Id"),
        )
        if member is None:
            raise workspace_access_denied()
        ensure_active_membership(
            str(user.status),
            str(member.workspace.status),
            str(member.role),
        )
        session.commit()
        return AuthContext(
            user_id=user.id,
            workspace_id=member.workspace_id,
            role=member.role,
            auth_source="supabase_jwt",
        )
    raise auth_mode_unsupported()


def _bearer_token(request: AuthRequestLike) -> str:
    authorization = request.headers.get("Authorization", "")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise auth_required()
    return authorization[len(prefix) :].strip()


__all__ = ["SupabaseJwtVerifier", "resolve_auth_context", "settings"]
