"""Compatibility wrapper.

Canonical owner: app.modules.account_ggr.contracts
Do not add new behavior here.
"""

from __future__ import annotations

import sys
from importlib import import_module

_contracts_module = import_module("app.modules.account_ggr.contracts")

GgrBreakdownRead = getattr(_contracts_module, "GgrBreakdownRead")
GgrBucket = getattr(_contracts_module, "GgrBucket")
GgrScoreRead = getattr(_contracts_module, "GgrScoreRead")

__all__ = ["GgrBreakdownRead", "GgrBucket", "GgrScoreRead"]

sys.modules[__name__] = _contracts_module
