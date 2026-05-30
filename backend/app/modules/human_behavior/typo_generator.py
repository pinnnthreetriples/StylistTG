"""Typo generator — probabilistic typo injection.

Stub version for tests: returns the typo text and a correction delay
without calling TDLib editMessageText.  The real integration happens
in behavior_aware_sender (a separate task).
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class TypoResult:
    """Outcome of a maybe_typo call."""

    original_text: str
    has_typo: bool
    typo_text: str | None
    correction_delay_seconds: float


def maybe_typo(
    text: str,
    probability: float,
    *,
    rng: random.Random | None = None,
) -> TypoResult:
    """With probability *p* inject a typo (swap two adjacent chars).

    Returns a TypoResult.  When ``has_typo`` is True the caller should
    send ``typo_text`` first, wait ``correction_delay_seconds``, then
    send an edit with the original ``original_text``.
    """
    r = rng or random.Random()

    if len(text) < 2 or probability <= 0.0:
        return TypoResult(
            original_text=text,
            has_typo=False,
            typo_text=None,
            correction_delay_seconds=0.0,
        )

    if r.random() >= probability:
        return TypoResult(
            original_text=text,
            has_typo=False,
            typo_text=None,
            correction_delay_seconds=0.0,
        )

    # Swap two adjacent characters
    pos = r.randint(0, len(text) - 2)
    chars = list(text)
    chars[pos], chars[pos + 1] = chars[pos + 1], chars[pos]
    typo_text = "".join(chars)

    # If the swap produced the same text (identical adjacent chars), still
    # report has_typo=True but typo_text == original_text is harmless.
    delay = r.uniform(0.2, 0.8)

    return TypoResult(
        original_text=text,
        has_typo=True,
        typo_text=typo_text,
        correction_delay_seconds=delay,
    )


__all__ = ["TypoResult", "maybe_typo"]
