"""Compatibility wrapper.

Canonical owner: app.modules.neuro_commenting.tdlib_helpers
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.neuro_commenting import tdlib_helpers as _canonical_module

sys.modules[__name__] = _canonical_module
