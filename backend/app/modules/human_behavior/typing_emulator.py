"""Typing emulator — simulate realistic typing cadence.

Returns a list of fragment timings without calling TDLib. The live
sender may consume this plan behind an explicit opt-in flag; this module
never performs Telegram side effects itself.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.observability.safety_metrics import safety_metrics


@dataclass(frozen=True)
class TypingFragment:
    """One segment of the typing simulation."""

    fragment_index: int
    chars_in_fragment: int
    duration_seconds: float
    pause_after_seconds: float


def emit_typing(
    text: str,
    cpm: float,
    *,
    rng: random.Random | None = None,
) -> list[TypingFragment]:
    """Plan typing simulation for text at cpm chars-per-minute."""
    try:
        if not text or cpm <= 0:
            safety_metrics.typing_emit(outcome="success")
            return []

        r = rng or random.Random()
        total_duration = len(text) * 60.0 / cpm
        num_fragments = r.randint(5, 15)
        char_counts = _distribute(len(text), num_fragments, r)
        fragments: list[TypingFragment] = []
        for i, chars in enumerate(char_counts):
            frac = chars / len(text) if len(text) > 0 else 1.0 / num_fragments
            frag_duration = total_duration * frac
            pause = r.uniform(0.05, 0.30) if i < len(char_counts) - 1 else 0.0
            fragments.append(
                TypingFragment(
                    fragment_index=i,
                    chars_in_fragment=chars,
                    duration_seconds=frag_duration,
                    pause_after_seconds=pause,
                )
            )

        safety_metrics.typing_emit(outcome="success")
        return fragments
    except Exception:
        safety_metrics.typing_emit(outcome="error")
        raise


def total_duration(fragments: list[TypingFragment]) -> float:
    """Sum of typing + pause durations."""
    return sum(f.duration_seconds + f.pause_after_seconds for f in fragments)


def _distribute(total: int, buckets: int, rng: random.Random) -> list[int]:
    if buckets <= 0:
        return []
    if buckets >= total:
        return [1] * total + [0] * (buckets - total)

    cuts = sorted(rng.sample(range(1, total), buckets - 1))
    parts: list[int] = []
    prev = 0
    for c in cuts:
        parts.append(c - prev)
        prev = c
    parts.append(total - prev)
    return parts
