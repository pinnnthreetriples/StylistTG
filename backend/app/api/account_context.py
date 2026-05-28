"""Compatibility wrapper.

Canonical owner: app.modules.account_core.context
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_core import context as _context_module

sys.modules[__name__] = _context_module
