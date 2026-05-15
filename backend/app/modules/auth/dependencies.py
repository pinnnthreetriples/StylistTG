from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.modules.auth.context import AuthContext
from app.modules.auth.policies import ensure_role_at_least
from app.modules.auth.service import resolve_auth_context


def get_current_auth_context(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> AuthContext:
    return resolve_auth_context(request, session)


def require_authenticated(
    context: Annotated[AuthContext, Depends(get_current_auth_context)],
) -> AuthContext:
    return context


def require_role(*roles: str):
    minimum = max(roles, key=lambda role: _role_sort_key(role))

    def dependency(context: Annotated[AuthContext, Depends(require_authenticated)]) -> AuthContext:
        return ensure_role_at_least(context, minimum)

    return dependency


def require_mutation_permission(
    context: Annotated[AuthContext, Depends(require_role("operator"))],
) -> AuthContext:
    return context


def _role_sort_key(role: str) -> int:
    from app.modules.auth.context import ROLE_ORDER
    from app.modules.auth.errors import role_invalid

    if role not in ROLE_ORDER:
        raise role_invalid()
    return ROLE_ORDER[role]


__all__ = [
    "get_current_auth_context",
    "require_authenticated",
    "require_mutation_permission",
    "require_role",
]
