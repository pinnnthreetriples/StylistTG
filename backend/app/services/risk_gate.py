"""Compatibility wrapper.
Canonical owner: app.modules.account_safety.action_gate.
Do not add new behavior here.
"""

from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("app.modules.account_safety.action_gate")
sys.modules[__name__] = _module
