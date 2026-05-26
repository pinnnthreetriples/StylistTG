"""Compatibility wrapper.

Canonical owner: app.modules.neuro_commenting.router
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.neuro_commenting import router as _router_module

sys.modules[__name__] = _router_module
