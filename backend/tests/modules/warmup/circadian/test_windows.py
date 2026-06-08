from __future__ import annotations

import random
from datetime import UTC, datetime

import pytest

from app.modules.warmup.circadian.windows import (
    hour_weight,
    is_lazy_day,
    pick_next_window,
)
from app.modules.warmup.dispatch_schedule import _schedule_within_day


def test_hour_weight_uses_default_human_rhythm() -> None:
    assert hour_weight(2, personality_seed={}) == 0.0
    assert hour_weight(13, personality_seed={}) == 1.0
    assert hour_weight(20, personality_seed={}) == 1.3


def test_evening_windows_are_sampled_more_than_daytime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.warmup_quiet_hours_local_start", 23)
    monkeypatch.setattr("app.config.settings.warmup_quiet_hours_local_end", 7)
    rng = random.Random(42)
    now = datetime(2026, 6, 5, 10, 0, tzinfo=UTC)
    hours = [
        pick_next_window(now, "UTC", rng=rng, personality_seed={"account_id": "a1"}).hour
        for _ in range(1000)
    ]

    evening = sum(1 for hour in hours if 19 <= hour <= 22)
    daytime = sum(1 for hour in hours if 15 <= hour <= 18)
    assert evening > daytime


def test_pick_next_window_respects_quiet_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.warmup_quiet_hours_local_start", 19)
    monkeypatch.setattr("app.config.settings.warmup_quiet_hours_local_end", 23)
    rng = random.Random(1)

    picked = pick_next_window(
        datetime(2026, 6, 5, 18, 0, tzinfo=UTC),
        "UTC",
        rng=rng,
        personality_seed={"account_id": "a1"},
    )

    assert picked.hour not in {19, 20, 21, 22}


def test_pick_next_window_boundary_invalid_timezone_falls_back_to_utc() -> None:
    now = datetime(2026, 6, 5, 10, 0, tzinfo=UTC)

    picked = pick_next_window(
        now,
        "Mars/Olympus_Mons",
        rng=random.Random(3),
        personality_seed={"account_id": "a1"},
    )

    assert picked.tzinfo == UTC
    assert picked > now


def test_lazy_day_is_deterministic_per_account_and_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.warmup_lazy_day_probability", 0.10)
    now = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)
    seed = {"account_id": "account-1"}

    first = is_lazy_day(now, personality_seed=seed, rng=random.Random(1))
    second = is_lazy_day(now, personality_seed=seed, rng=random.Random(999))

    assert first == second


def test_lazy_day_allows_only_one_same_day_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.warmup_circadian_enabled", True)
    monkeypatch.setattr("app.config.settings.warmup_lazy_day_probability", 1.0)
    now = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)
    last_window = datetime(2026, 6, 5, 9, 0, tzinfo=UTC)

    scheduled = _schedule_within_day(
        now,
        "UTC",
        rng=random.Random(2),
        personality_seed={"account_id": "account-1"},
        last_micro_session_at=last_window,
    )

    assert scheduled.date() > now.date()
