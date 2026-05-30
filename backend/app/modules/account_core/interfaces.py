"""Backwards-compatible re-export of the neutral `account_shared` facade.

These primitives now live in `app.modules.account_shared.interfaces`
so that downstream feature modules do not have to take a direct
dependency on `account_core` (which historically created
account_core <-> account_safety / warmup cycles).
"""

from __future__ import annotations

from app.modules.account_shared.interfaces import (
    build_account_capabilities,
    list_workspace_accounts,
    lookup_account,
)

__all__ = ["build_account_capabilities", "list_workspace_accounts", "lookup_account"]
