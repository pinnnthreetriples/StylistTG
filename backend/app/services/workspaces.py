"""Compatibility wrapper.
Canonical owner: app.workspace_bootstrap.
Do not add new behavior here.
"""

from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("app.workspace_bootstrap")
sys.modules[__name__] = _module
