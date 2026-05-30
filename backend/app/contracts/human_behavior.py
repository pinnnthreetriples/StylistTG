"""Compatibility wrapper.

Canonical owner: app.modules.human_behavior.contracts
Do not add new behavior here.
"""

from __future__ import annotations

import sys
from importlib import import_module

_contracts_module = import_module("app.modules.human_behavior.contracts")

BehaviorProfileRead = getattr(_contracts_module, "BehaviorProfileRead")

__all__ = ["BehaviorProfileRead"]

sys.modules[__name__] = _contracts_module
