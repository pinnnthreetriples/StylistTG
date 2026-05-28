"""Compatibility wrapper.

Canonical owner: app.modules.account_core.capabilities
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_core import capabilities as _capabilities_module
from app.modules.account_core.capabilities import (
    CAPABILITY_KEYS,
    build_account_capabilities,
)

__all__ = ["CAPABILITY_KEYS", "build_account_capabilities"]

sys.modules[__name__] = _capabilities_module
