"""Compatibility wrapper.

Canonical owner: app.modules.neuro_commenting.post_detector
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.neuro_commenting import post_detector as _canonical_module

sys.modules[__name__] = _canonical_module
