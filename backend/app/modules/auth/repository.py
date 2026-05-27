from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceMember
from app.services.users import get_or_create_external_user as _get_or_create_external_user
from app.services.workspace_onboarding import (
    ensure_personal_workspace as _ensure_personal_workspace,
)
from app.services.workspace_onboarding import (
    resolve_workspace_membership as _resolve_workspace_membership,
)
from app.workspace_bootstrap import ensure_default_workspace as _ensure_default_workspace


def ensure_default_workspace(session: Session) -> tuple[User, Workspace, WorkspaceMember]:
    return _ensure_default_workspace(session)


def get_or_create_external_user(
    session: Session,
    *,
    provider: str,
    external_user_id: str,
    email: str,
    display_name: str | None = None,
) -> User:
    return _get_or_create_external_user(
        session,
        provider=provider,
        external_user_id=external_user_id,
        email=email,
        display_name=display_name,
    )


def resolve_workspace_membership(
    session: Session,
    *,
    user: User,
    requested_workspace_id: str | None,
) -> WorkspaceMember | None:
    return _resolve_workspace_membership(
        session,
        user=user,
        requested_workspace_id=requested_workspace_id,
    )


def ensure_personal_workspace(session: Session, *, user: User) -> WorkspaceMember:
    return _ensure_personal_workspace(session, user=user)


__all__ = [
    "ensure_default_workspace",
    "ensure_personal_workspace",
    "get_or_create_external_user",
    "resolve_workspace_membership",
]
