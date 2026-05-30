"""Backwards-compatible re-export of capability composition.

Canonical implementation lives in `app.modules.account_shared.capabilities`
so that capability composition does not impose an
`account_safety -> account_core` dependency.
"""

from __future__ import annotations

from app.modules.account_shared.interfaces import (
    CAPABILITY_KEYS,
    build_account_capabilities,
)

__all__ = ["CAPABILITY_KEYS", "build_account_capabilities"]
