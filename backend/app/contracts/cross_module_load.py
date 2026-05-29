"""Compatibility wrapper.

Canonical owner: app.modules.account_core.cross_module_contracts
Do not add new behavior here.
"""

from __future__ import annotations

import sys
from importlib import import_module

_contracts_module = import_module("app.modules.account_core.cross_module_contracts")

CrossModuleLoad = getattr(_contracts_module, "CrossModuleLoad")
CrossModuleLoadBreakdown = getattr(_contracts_module, "CrossModuleLoadBreakdown")
CrossModuleName = getattr(_contracts_module, "CrossModuleName")

__all__ = ["CrossModuleLoad", "CrossModuleLoadBreakdown", "CrossModuleName"]

sys.modules[__name__] = _contracts_module
