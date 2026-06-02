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


def test_seeded_numpy_rng_returns_none_when_import_fails(monkeypatch) -> None:
    """Helper must degrade to ``None`` when NumPy cannot be imported.

    The test forces the ImportError path via a monkeypatched
    ``builtins.__import__`` so the contract holds regardless of whether
    NumPy is actually installed in the test environment.
    """
    import builtins

    real_import = builtins.__import__

    def _fake_import(name: str, *args, **kwargs):
        if name == "numpy" or name.startswith("numpy."):
            raise ImportError("numpy intentionally hidden for this test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    assert seeded_numpy_rng() is None


def test_seeded_numpy_rng_returns_deterministic_generator_when_available() -> None:
    """When NumPy is installed, the helper returns a seeded ``Generator``.

    Skipped when NumPy is absent — the negative-path contract is covered
    by ``test_seeded_numpy_rng_returns_none_when_import_fails``.
    """
    numpy = pytest.importorskip("numpy")

    rng_a = seeded_numpy_rng()
    rng_b = seeded_numpy_rng()
    assert rng_a is not None and rng_b is not None
    # Determinism: two generators built with the same default seed produce
    # the same sequence on the same NumPy version.
    assert numpy.array_equal(rng_a.standard_normal(5), rng_b.standard_normal(5))
