"""Compatibility wrapper.

Canonical owner: app.modules.human_behavior.behavior_profile
Do not add new behavior here.
"""

from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("app.modules.human_behavior.behavior_profile")
sys.modules[__name__] = _module
