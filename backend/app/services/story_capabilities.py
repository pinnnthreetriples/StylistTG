"""Compatibility wrapper.

Canonical owner: app.modules.story.capabilities
Do not add new behavior here.
"""

from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("app.modules.story.capabilities")
sys.modules[__name__] = _module
