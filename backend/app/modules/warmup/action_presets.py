from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.warmup_tdlib_contracts import SUPPORTED_ADVANCED_ACTIONS
from app.models import WarmupStrategy
from app.modules.warmup import read_models
from app.modules.warmup.contracts import WarmupStrategyRead
from app.modules.warmup.errors import WarmupStrategyNotFoundError
from app.services.audit_logs import log_audit_event

ActionPresetKind = Literal["economic", "all", "minimal"]

ALL_ACTIONS: tuple[str, ...] = tuple(dict.fromkeys(SUPPORTED_ADVANCED_ACTIONS))
ECONOMIC_ACTIONS: tuple[str, ...] = (
    "feed_read",
    "view_dialogs",
    "mark_as_read",
    "search_messages",
    "saved_messages",
    "check_settings",
)
MINIMAL_ACTIONS: tuple[str, ...] = ("feed_read", "view_dialogs")

_PRESET_ACTIONS: dict[ActionPresetKind, frozenset[str]] = {
    "economic": frozenset(ECONOMIC_ACTIONS),
    "all": frozenset(ALL_ACTIONS),
    "minimal": frozenset(MINIMAL_ACTIONS),
}
_DEFAULT_ENABLED_LIMIT = 1
_INT_COERCION_ERRORS = (TypeError, ValueError)


def apply_action_preset(
    daily_action_limits: dict[str, Any] | None,
    preset: ActionPresetKind,
    *,
    duration_days: int,
) -> dict[str, dict[str, int]]:
    enabled_actions = _PRESET_ACTIONS[preset]
    source = daily_action_limits or {}
    day_keys = _day_keys(source, duration_days)
    updated: dict[str, dict[str, int]] = {}
    for day_key in day_keys:
        raw_day_limits = source.get(day_key)
        current_limits = raw_day_limits if isinstance(raw_day_limits, dict) else {}
        updated[day_key] = {
            action_type: _next_limit(current_limits.get(action_type), action_type, enabled_actions)
            for action_type in ALL_ACTIONS
        }
    return updated


def apply_action_preset_use_case(
    session: Session,
    *,
    strategy_id: str,
    workspace_id: str,
    preset: ActionPresetKind,
    actor_user_id: str | None,
    applied_at: datetime | None = None,
) -> WarmupStrategyRead:
    strategy = _get_workspace_strategy(session, strategy_id=strategy_id, workspace_id=workspace_id)
    timestamp = applied_at or datetime.now(UTC)
    strategy.daily_action_limits_json = apply_action_preset(
        cast(dict[str, Any] | None, strategy.daily_action_limits_json),
        preset,
        duration_days=strategy.duration_days,
    )
    strategy.updated_at = timestamp
    log_audit_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="warmup_strategy_preset_applied",
        entity_type="warmup_strategy",
        entity_id=strategy.id,
        metadata={
            "preset": preset,
            "applied_at": timestamp.isoformat(),
            "actor_user_id": actor_user_id,
        },
    )
    session.commit()
    session.refresh(strategy)
    return read_models.strategy_read(strategy)


def _day_keys(source: dict[str, Any], duration_days: int) -> list[str]:
    if source:
        return sorted(source.keys(), key=_day_sort_key)
    return [str(day) for day in range(1, max(1, duration_days) + 1)]


def _day_sort_key(value: str) -> tuple[int, str]:
    try:
        return (int(value), value)
    except _INT_COERCION_ERRORS:
        return (10_000, value)


def _next_limit(value: Any, action_type: str, enabled_actions: frozenset[str]) -> int:
    if action_type not in enabled_actions:
        return 0
    try:
        current = int(value)
    except _INT_COERCION_ERRORS:
        current = 0
    return current if current > 0 else _DEFAULT_ENABLED_LIMIT


def _get_workspace_strategy(
    session: Session,
    *,
    strategy_id: str,
    workspace_id: str,
) -> WarmupStrategy:
    strategy = session.scalar(
        select(WarmupStrategy).where(
            WarmupStrategy.id == strategy_id,
            WarmupStrategy.workspace_id == workspace_id,
        )
    )
    if strategy is None:
        raise WarmupStrategyNotFoundError("strategy not found")
    return strategy


__all__ = [
    "ALL_ACTIONS",
    "ECONOMIC_ACTIONS",
    "MINIMAL_ACTIONS",
    "ActionPresetKind",
    "apply_action_preset",
    "apply_action_preset_use_case",
]
