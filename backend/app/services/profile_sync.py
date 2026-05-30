"""Compatibility wrapper.

Canonical owner: app.modules.account_profile_state.sync
Do not add new behavior here.
"""

from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("app.modules.account_profile_state.sync")
sys.modules[__name__] = _module
