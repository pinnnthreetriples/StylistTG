"""Compatibility wrapper.

Canonical owner: app.modules.bought_onboarding.service
Do not add new behavior here.
"""

from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("app.modules.bought_onboarding.service")
sys.modules[__name__] = _module
