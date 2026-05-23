"""Property-based tests for the Human Behavior Emulator modules."""

from __future__ import annotations

import random

import pytest
from hypothesis import HealthCheck
from hypothesis import given
from hypothesis import settings as h_settings
from hypothesis import strategies as st

from app.models import AccountBehaviorProfile
from app.services.human_behavior.action_sequencer import shuffle
from app.services.human_behavior.behavior_profile import randomize_for_session
from app.services.human_behavior.decoy_actions import run_before_send
from app.services.human_behavior.typing_emulator import emit_typing
from app.services.human_behavior.typing_emulator import total_duration
from app.services.human_behavior.typo_generator import maybe_typo

pytestmark = pytest.mark.property

_ACTIONS = ["view_profile", "scroll", "react", "comment", "read_messages"]


def _seeded_rng(seed: int = 42) -> random.Random:
    return random.Random(seed)


def _baseline_profile(
    *,
    typing_speed_baseline_cpm: int = 200,
    typo_rate_baseline: float = 0.02,
    profile_view_probability_baseline: float = 0.15,
    scroll_probability_baseline: float = 0.30,
    message_deletion_probability_baseline: float = 0.005,
) -> AccountBehaviorProfile:
    return AccountBehaviorProfile(
        id="profile-1",
        workspace_id="workspace-1",
        account_id="account-1",
        typing_speed_baseline_cpm=typing_speed_baseline_cpm,
        typo_rate_baseline=typo_rate_baseline,
        profile_view_probability_baseline=profile_view_probability_baseline,
        scroll_probability_baseline=scroll_probability_baseline,
        message_deletion_probability_baseline=message_deletion_probability_baseline,
        action_sequence_seed=123,
    )


@h_settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
@given(
    text=st.text(
        alphabet=st.characters(blacklist_categories=["Cs"]),
        min_size=10,
        max_size=500,
    ),
    cpm=st.integers(min_value=120, max_value=320),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
def test_typing_duration_within_tolerance(text: str, cpm: int, seed: int):
    fragments = emit_typing(text, float(cpm), rng=_seeded_rng(seed))
    expected = len(text) * 60.0 / cpm
    measured = sum(fragment.duration_seconds for fragment in fragments)
    assert expected * 0.85 <= measured <= expected * 1.15


@h_settings(max_examples=20, deadline=None)
@given(probability=st.sampled_from([0.005, 0.01, 0.025, 0.05, 0.075, 0.10]))
def test_typo_rate_converges(probability: float):
    iterations = 10_000
    rng = _seeded_rng(42)
    actual = (
        sum(
            1
            for _ in range(iterations)
            if maybe_typo("Hello world test", probability, rng=rng).has_typo
        )
        / iterations
    )
    assert abs(actual - probability) <= 0.005


@h_settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
@given(
    actions=st.lists(st.sampled_from(_ACTIONS), min_size=3, max_size=10),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
def test_shuffle_deterministic_same_seed(actions: list[str], seed: int):
    first = shuffle(list(actions), seed=seed)
    second = shuffle(list(actions), seed=seed)
    assert first == second


@h_settings(max_examples=20, deadline=None)
@given(baseline_cpm=st.integers(min_value=120, max_value=320), seed=st.integers())
def test_per_session_randomization_within_band(baseline_cpm: int, seed: int):
    profile = _baseline_profile(typing_speed_baseline_cpm=baseline_cpm)
    samples = [
        randomize_for_session(profile, rng=_seeded_rng(seed + offset)).typing_speed_cpm
        for offset in range(100)
    ]
    assert all(baseline_cpm * 0.90 <= sample <= baseline_cpm * 1.10 for sample in samples)


@h_settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
@given(
    text=st.text(
        alphabet=st.characters(blacklist_categories=["Cs"]),
        min_size=1,
        max_size=500,
    ),
    cpm=st.integers(min_value=120, max_value=320),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
def test_emit_typing_chunk_durations_sum_to_expected(text: str, cpm: int, seed: int):
    fragments = emit_typing(text, float(cpm), rng=_seeded_rng(seed))
    expected = len(text) * 60.0 / cpm
    measured = sum(fragment.duration_seconds for fragment in fragments)
    assert abs(measured - expected) <= 0.05


@h_settings(max_examples=20, deadline=None)
@given(probability=st.floats(min_value=0.05, max_value=0.95), seed=st.integers())
def test_decoy_action_probability_calibrates(probability: float, seed: int):
    iterations = 10_000
    rng = _seeded_rng(seed)
    actual = (
        sum(1 for _ in range(iterations) if run_before_send("account-1", probability, rng=rng))
        / iterations
    )
    assert abs(actual - probability) <= 0.02


def test_shuffle_seed_independence_statistical():
    actions = list("abcdefg")
    same = sum(
        1
        for seed in range(100)
        if shuffle(list(actions), seed=seed) == shuffle(list(actions), seed=seed + 1000)
    )
    assert same < 15


def test_total_duration_includes_pause_time():
    fragments = emit_typing("Human behavior emulator", 180.0, rng=_seeded_rng(7))
    typing_only = sum(fragment.duration_seconds for fragment in fragments)
    assert total_duration(fragments) >= typing_only


def test_boundary_empty_inputs_return_empty_plans():
    assert emit_typing("", 180.0, rng=_seeded_rng(7)) == []
    assert run_before_send("account-1", 0.0, rng=_seeded_rng(7)) == []
