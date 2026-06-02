"""Tests for the determinism helpers (issue #271)."""

# test-analyzer: disable-file=TQA012 reason="datetime.now() is called inside frozen_clock(); the assertion verifies the helper works"

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.helpers.determinism import (
    DEFAULT_FROZEN_INSTANT,
    DEFAULT_SEED,
    frozen_clock,
    seeded_numpy_rng,
    seeded_rng,
)

pytestmark = pytest.mark.unit


def test_frozen_clock_default_instant_is_stable() -> None:
    with frozen_clock():
        assert datetime.now(UTC) == DEFAULT_FROZEN_INSTANT


def test_frozen_clock_accepts_custom_instant() -> None:
    target = datetime(2027, 1, 1, tzinfo=UTC)
    with frozen_clock(target):
        assert datetime.now(UTC) == target


def test_seeded_rng_is_deterministic() -> None:
    a = seeded_rng().random()
    b = seeded_rng().random()
    assert a == b


def test_seeded_rng_uses_default_seed() -> None:
    expected = __import__("random").Random(DEFAULT_SEED).random()
    assert seeded_rng().random() == expected


def test_seeded_rng_accepts_explicit_seed() -> None:
    custom = seeded_rng(seed=42).random()
    expected = __import__("random").Random(42).random()
    assert custom == expected


def test_seeded_numpy_rng_returns_none_without_numpy() -> None:
    # NumPy is not in the backend test extra; the helper must degrade cleanly.
    result = seeded_numpy_rng()
    assert result is None
