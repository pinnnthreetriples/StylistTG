"""Compatibility wrapper.

Canonical owner: app.modules.account_core.cross_module_contracts
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_core import cross_module_contracts as _contracts_module
from app.modules.account_core.cross_module_contracts import (
    CrossModuleLoad,
    CrossModuleLoadBreakdown,
    CrossModuleName,
)

__all__ = ["CrossModuleLoad", "CrossModuleLoadBreakdown", "CrossModuleName"]

sys.modules[__name__] = _contracts_module
