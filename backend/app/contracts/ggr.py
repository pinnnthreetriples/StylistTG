"""Compatibility wrapper.
Canonical owner: app.modules.account_ggr.contracts.
Do not add new behavior here.
"""

from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("app.modules.account_ggr.contracts")
sys.modules[__name__] = _module
