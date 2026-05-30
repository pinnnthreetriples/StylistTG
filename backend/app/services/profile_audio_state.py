"""Compatibility wrapper.

Canonical owner: app.modules.account_profile_state.audio
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.account_profile_state import audio as _module
from app.modules.account_profile_state.audio import (
    clear_profile_audio_state,
    profile_audio_state_payload,
    upsert_profile_audio_state,
)

__all__ = [
    "clear_profile_audio_state",
    "profile_audio_state_payload",
    "upsert_profile_audio_state",
]

sys.modules[__name__] = _module
