from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    workspace_id: str
    role: str
    auth_source: str
    is_system: bool = False


ROLE_VIEWER = "viewer"
ROLE_OPERATOR = "operator"
ROLE_ADMIN = "admin"
ROLE_OWNER = "owner"

ROLE_ORDER = {
    ROLE_VIEWER: 0,
    ROLE_OPERATOR: 1,
    ROLE_ADMIN: 2,
    ROLE_OWNER: 3,
}


__all__ = [
    "AuthContext",
    "ROLE_ADMIN",
    "ROLE_OPERATOR",
    "ROLE_ORDER",
    "ROLE_OWNER",
    "ROLE_VIEWER",
]
