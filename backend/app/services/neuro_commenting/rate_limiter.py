"""Compatibility wrapper.

Canonical owner: app.modules.neuro_commenting.rate_limiter
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.neuro_commenting import rate_limiter as _canonical_module

sys.modules[__name__] = _canonical_module
