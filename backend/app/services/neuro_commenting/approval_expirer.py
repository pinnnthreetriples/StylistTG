"""Compatibility wrapper.

Canonical owner: app.modules.neuro_commenting.approval_expirer
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.neuro_commenting import approval_expirer as _canonical_module

sys.modules[__name__] = _canonical_module
