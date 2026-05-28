"""Compatibility wrapper.
Canonical owner: app.modules.human_behavior.router.
Do not add new behavior here.
"""

from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("app.modules.human_behavior.router")
sys.modules[__name__] = _module
