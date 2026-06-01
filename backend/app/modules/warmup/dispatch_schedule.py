from __future__ import annotations

import random
from datetime import UTC, datetime, time, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import settings
from app.models import WarmupSession

DEFAULT_ACTION_PRIORITY = ("feed_read", "join_chat", "p2p_send")
MAX_ACTIONS_PER_MICRO_SESSION = 3
_INT_COERCION_ERRORS = (TypeError, ValueError)


def _max_retry_after_seconds(failed_actions: list[dict[str, Any]]) -> int | None:
    values: list[int] = []
    for action in failed_actions:
        raw = action.get("retry_after_seconds")
        if raw is None:
            continue
        try:
            values.append(max(0, int(raw)))
        except _INT_COERCION_ERRORS:
            continue
    return max(values) if values else None


def _resolve_day_plan(warmup_session: WarmupSession) -> dict[str, int]:
    """Read daily_action_limits for the current day from the strategy snapshot.

    Contract: strategy daily_action_limits uses **1-based** day keys
    (``"1"``, ``"2"``, …). ``WarmupSession.current_day`` is 0-based, so we
    look up ``current_day + 1``.  Fallback to ``current_day`` key exists
    only for backward compatibility with legacy strategies that may have
    used 0-based keys — it will never match for correctly-seeded data.
    """
    limits = warmup_session.strategy.daily_action_limits_json or {}
    raw = limits.get(str(warmup_session.current_day + 1)) or limits.get(
        str(warmup_session.current_day)
    )
    if not isinstance(raw, dict):
        return {}
    plan: dict[str, int] = {}
    raw_items = cast(dict[object, object], raw)
    for key, value in raw_items.items():
        try:
            plan[str(key)] = max(0, int(cast(Any, value)))
        except _INT_COERCION_ERRORS:
            continue
    return plan


def _resolve_day_counters(warmup_session: WarmupSession) -> dict[str, int]:
    counters = warmup_session.daily_counters_json or {}
    raw = counters.get(str(warmup_session.current_day))
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    raw_items = cast(dict[object, object], raw)
    for key, value in raw_items.items():
        try:
            out[str(key)] = max(0, int(cast(Any, value)))
        except _INT_COERCION_ERRORS:
            continue
    return out


def _persist_day_counters(
    counters_json: dict[str, Any] | None,
    current_day: int,
    counters_for_day: dict[str, int],
) -> dict[str, Any]:
    counters = dict(counters_json or {})
    counters[str(current_day)] = dict(counters_for_day)
    return counters


def _select_actions_for_window(
    plan: dict[str, int],
    counters: dict[str, int],
    *,
    rng: random.Random,
) -> list[str]:
    """Pick which actions are simulated in this micro-session window.

    Conservative: at most one of each action type per window, capped at
    MAX_ACTIONS_PER_MICRO_SESSION. Action types ordered by
    DEFAULT_ACTION_PRIORITY first, then alphabetically for stability.
    """
    candidates = sorted(
        plan.keys(),
        key=lambda key: (
            DEFAULT_ACTION_PRIORITY.index(key)
            if key in DEFAULT_ACTION_PRIORITY
            else len(DEFAULT_ACTION_PRIORITY),
            key,
        ),
    )
    chosen: list[str] = []
    for key in candidates:
        if len(chosen) >= MAX_ACTIONS_PER_MICRO_SESSION:
            break
        budget = plan.get(key, 0) - counters.get(key, 0)
        if budget <= 0:
            continue
        # pick this action with small probabilistic drop to introduce jitter
        if rng.random() < 0.85:
            chosen.append(key)
    return chosen


def _is_day_complete(plan: dict[str, int], counters: dict[str, int]) -> bool:
    if not plan:
        return True
    for key, total in plan.items():
        if counters.get(key, 0) < total:
            return False
    return True


def _schedule_within_day(
    now: datetime, timezone_name: str | None, *, rng: random.Random
) -> datetime:
    span_min = max(1, settings.warmup_micro_session_min_minutes)
    span_max = max(span_min, settings.warmup_micro_session_max_minutes)
    # space windows out: jitter from one-window-length to several-window-lengths
    jitter_minutes = rng.randint(span_min * 6, span_max * 12)
    candidate = now + timedelta(minutes=jitter_minutes)
    if _is_in_quiet_hours(candidate, timezone_name):
        return _next_quiet_hours_end(candidate, timezone_name)
    return candidate


def _next_day_first_window(
    now: datetime, timezone_name: str | None, *, rng: random.Random
) -> datetime:
    base = now + timedelta(hours=12)
    jitter_minutes = rng.randint(0, 180)
    candidate = base + timedelta(minutes=jitter_minutes)
    if _is_in_quiet_hours(candidate, timezone_name):
        return _next_quiet_hours_end(candidate, timezone_name)
    return candidate


def _is_in_quiet_hours(moment: datetime, timezone_name: str | None) -> bool:
    local_hour = _local_hour(moment, timezone_name)
    return _is_hour_in_quiet_window(
        local_hour,
        settings.warmup_quiet_hours_local_start,
        settings.warmup_quiet_hours_local_end,
    )


def _is_hour_in_quiet_window(hour: int, start: int, end: int) -> bool:
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    # wraps midnight, e.g. 23 → 8
    return hour >= start or hour < end


def _next_quiet_hours_end(moment: datetime, timezone_name: str | None) -> datetime:
    """Return earliest UTC datetime strictly after `moment` whose local hour
    matches `warmup_quiet_hours_local_end` (i.e. quiet hours ended)."""
    tz = _resolve_timezone(timezone_name)
    local_now = moment.astimezone(tz)
    end_hour = settings.warmup_quiet_hours_local_end
    candidate_local = local_now.replace(hour=end_hour, minute=0, second=0, microsecond=0)
    if candidate_local <= local_now:
        candidate_local = candidate_local + timedelta(days=1)
    # Combine with date+end_hour ensures tz dst safety for our purposes
    candidate_local = datetime.combine(candidate_local.date(), time(hour=end_hour), tzinfo=tz)
    if candidate_local <= local_now:
        candidate_local = candidate_local + timedelta(days=1)
    return candidate_local.astimezone(UTC)


def _local_hour(moment: datetime, timezone_name: str | None) -> int:
    tz = _resolve_timezone(timezone_name)
    return moment.astimezone(tz).hour


def _resolve_timezone(timezone_name: str | None) -> ZoneInfo:
    if timezone_name:
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")
    return ZoneInfo("UTC")
