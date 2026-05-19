"""Action sequencer — deterministic seeded shuffle for planned actions."""

from __future__ import annotations

import random
from typing import TypeVar

T = TypeVar("T")


def shuffle(actions: list[T], seed: int) -> list[T]:
    """Return a new list with *actions* deterministically shuffled by *seed*.

    The same seed always produces the same permutation.  Different seeds
    produce different orders (with high probability).

    Dependency-preserving: this basic implementation does a full shuffle.
    For dependency-aware ordering, the caller must split independent
    groups, shuffle each, and concatenate respecting topological order.
    """
    if len(actions) <= 1:
        return list(actions)

    r = random.Random(seed)
    result = list(actions)
    r.shuffle(result)
    return result
