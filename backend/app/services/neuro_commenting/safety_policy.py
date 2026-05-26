"""Compatibility wrapper.

Canonical owner: app.modules.neuro_commenting.safety_policy
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.neuro_commenting import safety_policy as _canonical_module

sys.modules[__name__] = _canonical_module
