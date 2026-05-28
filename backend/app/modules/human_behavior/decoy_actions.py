"""Decoy actions — pre-send noise plan that never invokes TDLib itself."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class DecoyAction:
    """One decoy action that a gated live sender may execute."""

    kind: str
    target_id: str | None


def run_before_send(
    account_id: str,
    profile_view_probability: float,
    *,
    rng: random.Random | None = None,
) -> list[DecoyAction]:
    _ = account_id
    r = rng or random.Random()

    if profile_view_probability <= 0.0:
        return []

    if r.random() >= profile_view_probability:
        return []

    count = r.randint(1, 3)
    actions: list[DecoyAction] = []
    for _ in range(count):
        kind = r.choice(["getUser", "getChat"])
        actions.append(DecoyAction(kind=kind, target_id=None))

    return actions
