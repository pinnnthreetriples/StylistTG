"""Compatibility wrapper.

Canonical owner: app.modules.account_lifecycle.router
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_lifecycle import router as _router_module

sys.modules[__name__] = _router_module
