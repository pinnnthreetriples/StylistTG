"""Compatibility wrapper.

Canonical owner: app.modules.account_audit.router
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_audit import router as _router_module
from app.modules.account_audit.router import router

__all__ = ["router"]

sys.modules[__name__] = _router_module
