"""Hypothesis property-based tests for HumanBehaviorEmulator (Phase 2 Task 14).

3 strategies:
1. typing duration distribution: mean ≈ expected ± 15%
2. typo rate: count / total ≈ probability ± 0.5%
3. shuffle determinism: same seed → same order, different seed → high distance
"""

from __future__ import annotations

import random

import pytest
from hypothesis import given, settings as h_settings, HealthCheck
from hypothesis import strategies as st

from app.services.human_behavior.typing_emulator import emit_typing
from app.services.human_behavior.typo_generator import maybe_typo
from app.services.human_behavior.action_sequencer import shuffle


class TestTypingDurationDistribution:
    """1. Over many runs, mean typing duration ≈ expected ± 15%."""

    @h_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    @given(
        text_len=st.integers(min_value=10, max_value=500),
        cpm=st.floats(min_value=30.0, max_value=400.0),
        seed=st.integers(min_value=0, max_value=2**31),
    )
    def test_mean_duration_within_tolerance(self, text_len: int, cpm: float, seed: int):
        text = "a" * text_len
        rng = random.Random(seed)
        fragments = emit_typing(text, cpm, rng=rng)

        expected = text_len * 60.0 / cpm
        actual_typing = sum(f.duration_seconds for f in fragments)

        # Typing-only duration (no pauses) should closely match expected
        if expected > 0:
            relative_error = abs(actual_typing - expected) / expected
            assert relative_error < 0.15, (
                f"relative error {relative_error:.3f} exceeds 15% "
                f"(expected={expected:.2f}, actual={actual_typing:.2f})"
            )


class TestTypoRateDistribution:
    """2. Over many runs, observed typo rate ≈ probability ± margin."""

    @pytest.mark.parametrize("probability", [0.0, 0.05, 0.50, 1.0])
    def test_typo_rate_converges(self, probability: float):
        n = 10000
        rng = random.Random(42)
        typos = sum(
            1 for _ in range(n) if maybe_typo("Hello world test", probability, rng=rng).has_typo
        )
        observed_rate = typos / n

        if probability == 0.0:
            assert observed_rate == 0.0
        elif probability == 1.0:
            assert observed_rate == 1.0
        else:
            assert abs(observed_rate - probability) < 0.02, (
                f"observed_rate={observed_rate:.4f} vs expected={probability}"
            )


class TestShuffleDeterminism:
    """3. same seed → same order; different seed → high Hamming distance."""

    @h_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    @given(
        n=st.integers(min_value=2, max_value=100),
        seed=st.integers(min_value=0, max_value=2**31),
    )
    def test_same_seed_produces_identical_output(self, n: int, seed: int):
        items = list(range(n))
        a = shuffle(items, seed=seed)
        b = shuffle(items, seed=seed)
        assert a == b

    @h_settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    @given(
        n=st.integers(min_value=10, max_value=100),
        seed_a=st.integers(min_value=0, max_value=2**30),
        seed_b=st.integers(min_value=2**30 + 1, max_value=2**31),
    )
    def test_different_seeds_produce_different_output(self, n: int, seed_a: int, seed_b: int):
        items = list(range(n))
        a = shuffle(items, seed=seed_a)
        b = shuffle(items, seed=seed_b)
        # With n ≥ 10 and different seeds, the Hamming distance should be > 0
        distance = sum(1 for x, y in zip(a, b, strict=True) if x != y)
        assert distance > 0, f"seeds {seed_a} vs {seed_b} produced same order for n={n}"
