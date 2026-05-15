from __future__ import annotations

from app.modules.auth.context import ROLE_ORDER, AuthContext
from app.modules.auth.errors import role_forbidden, role_invalid, user_disabled, workspace_disabled


ACTIVE_STATUS = "active"


def role_at_least(role: str, minimum_role: str) -> bool:
    if role not in ROLE_ORDER or minimum_role not in ROLE_ORDER:
        raise role_invalid()
    return ROLE_ORDER[role] >= ROLE_ORDER[minimum_role]


def ensure_role_at_least(context: AuthContext, minimum_role: str) -> AuthContext:
    if not role_at_least(context.role, minimum_role):
        raise role_forbidden()
    return context


def ensure_active_membership(user_status: str, workspace_status: str, role: str) -> None:
    if user_status != ACTIVE_STATUS:
        raise user_disabled()
    if workspace_status != ACTIVE_STATUS:
        raise workspace_disabled()
    if role not in ROLE_ORDER:
        raise role_invalid()


__all__ = [
    "ACTIVE_STATUS",
    "ensure_active_membership",
    "ensure_role_at_least",
    "role_at_least",
]
