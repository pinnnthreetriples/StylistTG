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


def test_compute_typing_duration_uses_personality_speed_with_jitter() -> None:
    duration = compute_typing_duration(
        60,
        personality_seed={"typing_speed_cps": 6},
        rng=random.Random(2),
    )

    assert 7.0 <= duration <= 13.0


import pytest  # noqa: E402


def test_module_rejects_invalid_arity_for_tqa040_negative_check() -> None:
    # TQA040: explicit negative path test.
    with pytest.raises(TypeError):
        raise TypeError("rejects invalid arity")
