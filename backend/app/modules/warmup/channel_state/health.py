from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol

HEALTH_THRESHOLD_EXCLUDE = 0.25
HEALTH_THRESHOLD_WARN = 0.50
_MAX_STALE_PENALTY = 0.20
_STALE_GRACE = timedelta(days=1)
_STALE_FULL_DECAY = timedelta(days=7)


class ChannelHealthState(Protocol):
    health_score: float


def compute_health_score(
    success_count: int,
    fail_count: int,
    last_success_at: datetime | None,
    now: datetime,
) -> float:
    success_count = max(0, success_count)
    fail_count = max(0, fail_count)
    if success_count == 0 and fail_count == 0:
        return 1.0

    score = (success_count + 1) / (success_count + fail_count + 2)
    score -= _stale_penalty(last_success_at, now)
    return _clamp(score)


def is_channel_healthy(
    state: ChannelHealthState, *, threshold: float = HEALTH_THRESHOLD_EXCLUDE
) -> bool:
    return state.health_score >= threshold


def _stale_penalty(last_success_at: datetime | None, now: datetime) -> float:
    if last_success_at is None:
        return 0.0
    last_success_at = _align_tz(last_success_at, now)
    age = now - last_success_at
    if age <= _STALE_GRACE:
        return 0.0
    decay_window = _STALE_FULL_DECAY - _STALE_GRACE
    return min(_MAX_STALE_PENALTY, (age - _STALE_GRACE) / decay_window * _MAX_STALE_PENALTY)


def _align_tz(value: datetime, now: datetime) -> datetime:
    if value.tzinfo is None and now.tzinfo is not None:
        return value.replace(tzinfo=now.tzinfo)
    if value.tzinfo is not None and now.tzinfo is None:
        return value.replace(tzinfo=None)
    return value


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, round(value, 4)))
