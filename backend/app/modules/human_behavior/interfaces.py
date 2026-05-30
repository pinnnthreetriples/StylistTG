"""Public cross-module facade for human_behavior."""

from __future__ import annotations

from app.modules.human_behavior.action_sequencer import shuffle
from app.modules.human_behavior.behavior_profile import (
    PRESET_RANGES,
    SessionProfile,
    get_or_create_baseline,
    randomize_for_session,
)
from app.modules.human_behavior.contracts import BehaviorProfileRead
from app.modules.human_behavior.decoy_actions import DecoyAction, run_before_send
from app.modules.human_behavior.typing_emulator import (
    TypingFragment,
    emit_typing,
    total_duration,
)
from app.modules.human_behavior.typo_generator import TypoResult, maybe_typo

__all__ = [
    "BehaviorProfileRead",
    "DecoyAction",
    "PRESET_RANGES",
    "SessionProfile",
    "TypingFragment",
    "TypoResult",
    "emit_typing",
    "get_or_create_baseline",
    "maybe_typo",
    "randomize_for_session",
    "run_before_send",
    "shuffle",
    "total_duration",
]
