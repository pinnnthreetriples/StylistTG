"""Decoy actions — pre-send noise that mimics real user behaviour.

Records *what* would be called (getUser / getChat) without invoking
TDLib. The live sender may consume this plan behind an explicit opt-in
flag; this module never performs Telegram side effects itself.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class DecoyAction:
    """One decoy action that should be executed before the real send."""

    kind: str  # "getUser" | "getChat"
    target_id: str | None


def run_before_send(
    account_id: str,
    profile_view_probability: float,
    *,
    rng: random.Random | None = None,
) -> list[DecoyAction]:
    """With probability *p* generate decoy actions (getUser / getChat).

    Returns a (possibly empty) list of actions.  The caller is
    responsible for executing them via TDLib.
    """
    r = rng or random.Random()

    if profile_view_probability <= 0.0:
        return []

    if r.random() >= profile_view_probability:
        return []

    # Pick 1-3 decoy actions
    count = r.randint(1, 3)
    actions: list[DecoyAction] = []
    for _ in range(count):
        kind = r.choice(["getUser", "getChat"])
        actions.append(DecoyAction(kind=kind, target_id=None))

    return actions
