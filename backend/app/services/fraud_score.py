"""Compatibility wrapper.
Canonical owner: app.modules.account_ggr.fraud_score.
Do not add new behavior here.
"""

from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("app.modules.account_ggr.fraud_score")
sys.modules[__name__] = _module
