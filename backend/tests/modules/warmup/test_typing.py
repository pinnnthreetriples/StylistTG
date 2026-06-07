import random

from app.modules.warmup.typing import compute_typing_duration


def test_compute_typing_duration_clamps_short_text_to_two_seconds() -> None:
    duration = compute_typing_duration(
        1,
        personality_seed={"typing_speed_cps": 100},
        rng=random.Random(1),
    )

    assert duration == 2.0


def test_compute_typing_duration_clamps_long_text_to_fifteen_seconds() -> None:
    duration = compute_typing_duration(
        10_000,
        personality_seed={"typing_speed_cps": 5},
        rng=random.Random(1),
    )

    assert duration == 15.0


def test_compute_typing_duration_boundary_rejects_negative_text_length() -> None:
    duration = compute_typing_duration(
        -20,
        personality_seed={"typing_speed_cps": 5},
        rng=random.Random(1),
    )

    assert duration == 2.0


def test_compute_typing_duration_uses_personality_speed_with_jitter() -> None:
    duration = compute_typing_duration(
        60,
        personality_seed={"typing_speed_cps": 6},
        rng=random.Random(2),
    )

    assert 7.0 <= duration <= 13.0


def test_compute_typing_duration_invalid_speed_falls_back_to_default() -> None:
    duration = compute_typing_duration(
        60,
        personality_seed={"typing_speed_cps": "fast"},
        rng=random.Random(2),
    )

    assert 2.0 <= duration <= 15.0
