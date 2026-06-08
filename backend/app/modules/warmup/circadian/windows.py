from __future__ import annotations

import random
from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import settings


DEFAULT_HOUR_WEIGHTS: dict[int, float] = {
    7: 0.3,
    8: 0.5,
    9: 0.7,
    10: 0.8,
    11: 0.7,
    12: 1.0,
    13: 1.0,
    14: 0.9,
    15: 0.6,
    16: 0.5,
    17: 0.6,
    18: 0.7,
    19: 1.2,
    20: 1.3,
    21: 1.2,
    22: 0.8,
    23: 0.1,
    0: 0.0,
    1: 0.0,
    2: 0.0,
    3: 0.0,
    4: 0.0,
    5: 0.0,
    6: 0.1,
}


def hour_weight(hour: int, *, personality_seed: dict[str, Any] | None = None) -> float:
    _ = personality_seed
    return max(0.0, min(1.5, float(DEFAULT_HOUR_WEIGHTS.get(hour % 24, 0.0))))


def pick_next_window(
    now: datetime,
    timezone: str | None,
    *,
    rng: random.Random,
    personality_seed: dict[str, Any] | None = None,
) -> datetime:
    zone = _zone(timezone)
    local_now = _aware(now).astimezone(zone)
    slots = _candidate_slots(local_now, zone, personality_seed or {})
    if not slots:
        return (now + timedelta(hours=1)).astimezone(UTC)
    selected = _weighted_choice(slots, rng)
    min_minute = (
        local_now.minute + 1
        if selected.date() == local_now.date() and selected.hour == local_now.hour
        else 0
    )
    minute = rng.randint(min(min_minute, 59), 59)
    candidate = selected.replace(minute=minute, second=0, microsecond=0)
    if candidate <= local_now:
        candidate = candidate + timedelta(hours=1)
    return candidate.astimezone(UTC)


def is_lazy_day(
    now: datetime,
    *,
    personality_seed: dict[str, Any] | None = None,
    rng: random.Random | None = None,
) -> bool:
    _ = rng
    probability = max(0.0, min(1.0, float(settings.warmup_lazy_day_probability)))
    if probability <= 0:
        return False
    seed_key = f"{(personality_seed or {}).get('account_id', 'account')}|{_aware(now).date()}"
    digest = sha256(seed_key.encode("utf-8")).hexdigest()
    day_rng = random.Random(int(digest[:16], 16))
    return day_rng.random() < probability


def _candidate_slots(
    local_now: datetime,
    zone: ZoneInfo,
    personality_seed: dict[str, Any],
) -> list[tuple[datetime, float]]:
    base = local_now.replace(minute=0, second=0, microsecond=0)
    slots: list[tuple[datetime, float]] = []
    for offset in range(13):
        slot = base + timedelta(hours=offset)
        if slot + timedelta(minutes=59) <= local_now:
            continue
        weight = hour_weight(slot.hour, personality_seed=personality_seed)
        if weight <= 0 or _is_hour_in_quiet_window(
            slot.hour,
            settings.warmup_quiet_hours_local_start,
            settings.warmup_quiet_hours_local_end,
        ):
            continue
        slots.append((_local_datetime(slot.date(), slot.hour, zone), weight))
    return slots


def _weighted_choice(slots: list[tuple[datetime, float]], rng: random.Random) -> datetime:
    total = sum(weight for _slot, weight in slots)
    threshold = rng.random() * total
    cumulative = 0.0
    for slot, weight in slots:
        cumulative += weight
        if threshold <= cumulative:
            return slot
    return slots[-1][0]


def _is_hour_in_quiet_window(hour: int, start: int, end: int) -> bool:
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def _local_datetime(day: date, hour: int, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, time(hour=hour), tzinfo=zone)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _zone(timezone: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(timezone or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


__all__ = [
    "DEFAULT_HOUR_WEIGHTS",
    "hour_weight",
    "is_lazy_day",
    "pick_next_window",
]
