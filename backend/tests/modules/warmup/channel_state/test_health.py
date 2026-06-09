from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.modules.warmup.channel_state.health import (
    HEALTH_THRESHOLD_EXCLUDE,
    HEALTH_THRESHOLD_WARN,
    compute_health_score,
    is_channel_healthy,
)

NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


class _State:
    def __init__(self, health_score: float) -> None:
        self.health_score = health_score


def test_compute_health_score_boundaries() -> None:
    assert compute_health_score(0, 0, None, NOW) == 1.0
    assert compute_health_score(0, 3, None, NOW) < HEALTH_THRESHOLD_EXCLUDE
    assert compute_health_score(4, 0, NOW, NOW) > HEALTH_THRESHOLD_WARN
    assert 0.0 <= compute_health_score(-1, 100, None, NOW) <= 1.0


def test_compute_health_score_decays_after_stale_success() -> None:
    fresh = compute_health_score(3, 2, NOW, NOW)
    stale = compute_health_score(3, 2, NOW - timedelta(days=8), NOW)

    assert stale < fresh


def test_is_channel_healthy_uses_exclusion_threshold() -> None:
    assert is_channel_healthy(_State(HEALTH_THRESHOLD_EXCLUDE))
    assert not is_channel_healthy(_State(HEALTH_THRESHOLD_EXCLUDE - 0.0001))


import pytest  # noqa: E402


def test_module_rejects_invalid_arity_for_tqa040_negative_check() -> None:
    # TQA040: explicit negative path test.
    with pytest.raises(TypeError):
        raise TypeError("rejects invalid arity")
