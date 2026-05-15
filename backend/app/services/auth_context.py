"""Compatibility wrapper.

Canonical owner: app.modules.auth.dependencies / context
Do not add new behavior here.
"""

from __future__ import annotations

from app.modules.auth.context import AuthContext, ROLE_ORDER
from app.modules.auth.dependencies import (
    get_current_auth_context,
    require_authenticated,
    require_mutation_permission,
    require_role,
)
from app.modules.auth.service import SupabaseJwtVerifier, settings


__all__ = [
    "AuthContext",
    "ROLE_ORDER",
    "SupabaseJwtVerifier",
    "get_current_auth_context",
    "require_authenticated",
    "require_mutation_permission",
    "require_role",
    "settings",
]
