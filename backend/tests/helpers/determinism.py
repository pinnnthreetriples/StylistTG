"""Determinism helpers for the PR pytest profile (issue #271).

Centralises the small primitives every flaky-prone test needs:

- :func:`frozen_clock` — context manager around ``freezegun.freeze_time``
  with a fixed default instant so callers don't reach for ``datetime.now()``.
- :func:`seeded_rng` — :class:`random.Random` instance with a deterministic
  default seed.
- :func:`seeded_numpy_rng` — optional NumPy generator companion (returns
  ``None`` if NumPy is not installed; tests that need it must import
  NumPy at the call site).

These helpers are intentionally tiny: their job is to make the
deterministic path the *easy* path, not to replace ``freezegun`` or
``random`` directly. Existing call sites that already pass an explicit
seed remain valid.

Determinism policy is documented in ``docs/quality/QUALITY_GATES.md``.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

DEFAULT_FROZEN_INSTANT = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
DEFAULT_SEED = 0xC0FFEE


@contextmanager
def frozen_clock(instant: datetime | None = None) -> Iterator[datetime]:
    """Freeze the wall clock at ``instant`` (default: 2026-06-02 12:00 UTC).

    Imports ``freezegun`` lazily so tests that do not need it pay nothing.
    """
    from freezegun import freeze_time

    target = instant or DEFAULT_FROZEN_INSTANT
    with freeze_time(target):
        yield target


def seeded_rng(seed: int | None = None) -> random.Random:
    """Return a :class:`random.Random` seeded with ``seed`` (default DEFAULT_SEED)."""
    return random.Random(seed if seed is not None else DEFAULT_SEED)


def seeded_numpy_rng(seed: int | None = None) -> Any | None:
    """Return a NumPy ``Generator`` if NumPy is installed, otherwise ``None``."""
    try:
        import numpy as np  # type: ignore[import-not-found]
    except ImportError:
        return None
    return np.random.default_rng(seed if seed is not None else DEFAULT_SEED)
