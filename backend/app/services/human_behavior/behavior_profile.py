"""Compatibility wrapper.

Canonical owner: app.modules.human_behavior.behavior_profile
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.human_behavior import behavior_profile as _module
from app.modules.human_behavior.behavior_profile import (
    PRESET_RANGES,
    SessionProfile,
    get_or_create_baseline,
    randomize_for_session,
)

__all__ = [
    "PRESET_RANGES",
    "SessionProfile",
    "get_or_create_baseline",
    "randomize_for_session",
]

sys.modules[__name__] = _module
