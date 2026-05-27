"""Compatibility wrapper.

Canonical owner: app.modules.account_profile_completeness.contracts
Do not add new behavior here.
"""

from __future__ import annotations

import importlib
import sys

_contracts_module = importlib.import_module("app.modules.account_profile_completeness.contracts")
sys.modules[__name__] = _contracts_module
