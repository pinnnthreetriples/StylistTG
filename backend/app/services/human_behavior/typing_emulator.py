"""Compatibility wrapper.

Canonical owner: app.modules.human_behavior.typing_emulator
Do not add new behavior here.
"""

from __future__ import annotations

import sys

from app.modules.human_behavior import typing_emulator as _module
from app.modules.human_behavior.typing_emulator import (
    TypingFragment,
    emit_typing,
    total_duration,
)

__all__ = ["TypingFragment", "emit_typing", "total_duration"]

sys.modules[__name__] = _module
