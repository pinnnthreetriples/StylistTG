from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import ceil
from typing import Any, cast

from app.models import WarmupSession

MIN_ADAPTIVE_MULTIPLIER = 0.25
MAX_ADAPTIVE_MULTIPLIER = 2.0
ADAPTIVE_ACCELERATE_MULTIPLIER = 1.2
ADAPTIVE_SLOWDOWN_MULTIPLIER = 0.5
ADAPTIVE_NEUTRAL_MULTIPLIER = 1.0
ADAPTIVE_LOOKBACK_DAYS = 3


@dataclass(frozen=True)
class PlanAdjustment:
    multipliers: dict[str, float]
    multiplier: float
    reason: str | None = None

    @property
    def is_active(self) -> bool:
        return self.reason is not None and self.multiplier != ADAPTIVE_NEUTRAL_MULTIPLIER

    @property
    def event_type(self) -> str | None:
        if self.reason == "3_clean_days":
            return "plan_adjusted_up"
        if self.reason in {"recent_failures", "flood_wait"}:
            return "plan_adjusted_down"
        return None


def compute_next_day_adjustment(warmup_session: WarmupSession, now: datetime) -> dict[str, float]:
    del now
    return describe_next_day_adjustment(warmup_session).multipliers


def describe_next_day_adjustment(warmup_session: WarmupSession) -> PlanAdjustment:
    action_types = _strategy_action_types(warmup_session)
    if not _is_adaptive_enabled(warmup_session) or not action_types:
        return PlanAdjustment({}, ADAPTIVE_NEUTRAL_MULTIPLIER)

    snapshots = _recent_day_counters(warmup_session)
    if len(snapshots) < ADAPTIVE_LOOKBACK_DAYS:
        return _adjustment(action_types, ADAPTIVE_NEUTRAL_MULTIPLIER, None)

    failures = sum(_counter_value(snapshot, "failures") for snapshot in snapshots)
    flood_waits = sum(_counter_value(snapshot, "flood_waits") for snapshot in snapshots)
    if flood_waits > 0:
        return _adjustment(action_types, ADAPTIVE_SLOWDOWN_MULTIPLIER, "flood_wait")
    if failures > 0:
        return _adjustment(action_types, ADAPTIVE_SLOWDOWN_MULTIPLIER, "recent_failures")
    return _adjustment(action_types, ADAPTIVE_ACCELERATE_MULTIPLIER, "3_clean_days")


def apply_plan_adjustment(plan: dict[str, int], adjustment: dict[str, float]) -> dict[str, int]:
    adjusted: dict[str, int] = {}
    for action_type, limit in plan.items():
        multiplier = _clamp_multiplier(adjustment.get(action_type, ADAPTIVE_NEUTRAL_MULTIPLIER))
        if limit <= 0:
            adjusted[action_type] = 0
        else:
            adjusted[action_type] = max(1, int(ceil(limit * multiplier)))
    return adjusted


def _is_adaptive_enabled(warmup_session: WarmupSession) -> bool:
    config = warmup_session.strategy.session_window_config_json or {}
    if config.get("adaptive_enabled") is True:
        return True
    adaptive = config.get("adaptive")
    if not isinstance(adaptive, dict):
        return False
    return cast(dict[str, Any], adaptive).get("enabled") is True


def _strategy_action_types(warmup_session: WarmupSession) -> list[str]:
    limits = warmup_session.strategy.daily_action_limits_json or {}
    actions: list[str] = []
    seen: set[str] = set()
    for raw in limits.values():
        if not isinstance(raw, dict):
            continue
        raw_limits = cast(dict[Any, Any], raw)
        for action_type, limit in raw_limits.items():
            if not isinstance(action_type, str) or action_type in seen:
                continue
            if _coerce_int(limit) <= 0:
                continue
            seen.add(action_type)
            actions.append(action_type)
    return actions


def _recent_day_counters(warmup_session: WarmupSession) -> list[dict[str, Any]]:
    counters = warmup_session.daily_counters_json or {}
    snapshots: list[dict[str, Any]] = []
    start = warmup_session.current_day - ADAPTIVE_LOOKBACK_DAYS
    if start < 0:
        return []
    for day in range(start, warmup_session.current_day):
        raw = counters.get(str(day))
        if not isinstance(raw, dict):
            return []
        snapshots.append(cast(dict[str, Any], raw))
    return snapshots


def _adjustment(action_types: list[str], multiplier: float, reason: str | None) -> PlanAdjustment:
    clamped = _clamp_multiplier(multiplier)
    return PlanAdjustment({action_type: clamped for action_type in action_types}, clamped, reason)


def _counter_value(snapshot: dict[str, Any], key: str) -> int:
    return max(0, _coerce_int(snapshot.get(key, 0)))


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except TypeError, ValueError:
        return 0


def _clamp_multiplier(value: float) -> float:
    return min(MAX_ADAPTIVE_MULTIPLIER, max(MIN_ADAPTIVE_MULTIPLIER, value))
