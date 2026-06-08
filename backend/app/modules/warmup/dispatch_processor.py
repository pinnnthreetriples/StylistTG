from __future__ import annotations

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

import random
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.adapters.warmup_text_provider import WarmupTextProvider
from app.adapters.warmup_tdlib import WarmupTdlibAdapter
from app.models import WarmupExecutionMode, WarmupSession, WarmupStatus
from app.modules.warmup.cold_soak import (
    advance_from_cold_soak,
    is_cold_soak_complete,
    record_cold_soak_in_progress,
)
from app.modules.warmup.channel_state.repository import get_states_for_account
from app.modules.warmup.cyclic import cycle_window_status, schedule_next_cycle
from app.modules.warmup.adaptive_plan import describe_next_day_adjustment
from app.modules.warmup.events import write_warmup_event
from app.modules.warmup.worker import handle_warmup_step_failure

from .dispatch_actions import _dispatch_action
from .dispatch_context import _pause_if_blocked_by_safety_gate, _target_channel_refs
from .dispatch_results import (
    _complete_dispatch_session,
    _record_dispatch_action_failure,
    _record_dispatch_action_success,
)
from .dispatch_schedule import (
    _is_day_complete,
    _is_in_quiet_hours,
    _max_retry_after_seconds,
    _next_day_first_window,
    _next_quiet_hours_end,
    _persist_day_counters,
    _resolve_day_counters,
    _resolve_day_plan,
    _schedule_within_day,
    _select_action_targets,
)

_LIVE_EXECUTION_MODES: frozenset[str] = frozenset(
    {
        WarmupExecutionMode.PASSIVE.value,
        WarmupExecutionMode.NETWORK.value,
        WarmupExecutionMode.ADVANCED.value,
    }
)


def _process_one_dispatch(
    session: Session,
    warmup_session: WarmupSession,
    *,
    now: datetime,
    worker_id: str,
    rng: random.Random,
    adapter: WarmupTdlibAdapter,
    text_provider: WarmupTextProvider,
) -> bool:
    if warmup_session.status == WarmupStatus.COLD_SOAK.value:
        if not is_cold_soak_complete(warmup_session, now):
            record_cold_soak_in_progress(session, warmup_session, now)
            return False
        advance_from_cold_soak(session, warmup_session, now)

    if _skip_if_outside_cyclic_window(session, warmup_session, now):
        return False

    if _is_in_quiet_hours(now, warmup_session.timezone):
        quiet_hours_end = _next_quiet_hours_end(now, warmup_session.timezone)
        warmup_session.next_micro_session_at = quiet_hours_end
        warmup_session.updated_at = now
        write_warmup_event(
            session,
            warmup_session,
            "task_skipped",
            {
                "reason": "quiet_hours",
                "reschedule_at": quiet_hours_end.isoformat(),
            },
        )
        session.flush()
        return False

    is_live = warmup_session.execution_mode in _LIVE_EXECUTION_MODES
    if _pause_if_blocked_by_safety_gate(
        session,
        warmup_session=warmup_session,
        now=now,
        worker_id=worker_id,
    ):
        return True
    if is_live and not adapter.is_available():
        warmup_session.next_micro_session_at = _schedule_within_day(
            now, warmup_session.timezone, rng=rng
        )
        warmup_session.next_step_at = warmup_session.next_micro_session_at
        warmup_session.updated_at = now
        write_warmup_event(
            session,
            warmup_session,
            "task_skipped",
            {
                "reason": "passive_disabled",
                "execution_mode": warmup_session.execution_mode,
                "provider": getattr(adapter, "provider_name", "unknown"),
            },
        )
        session.flush()
        return False

    plan_for_day = _resolve_day_plan(warmup_session)
    counters_for_day = _resolve_day_counters(warmup_session)
    available_targets = _target_channel_refs(warmup_session)
    channel_states = get_states_for_account(
        session,
        warmup_session.workspace_id,
        warmup_session.account_id,
        available_targets,
    )
    selected_actions = _select_action_targets(
        plan_for_day,
        counters_for_day,
        channel_states=channel_states,
        available_targets=available_targets,
        rng=rng,
        now=now,
    )

    write_warmup_event(
        session,
        warmup_session,
        "micro_session_window_opened",
        {
            "day": warmup_session.current_day,
            "execution_mode": warmup_session.execution_mode,
            "planned_actions": [selection.action_type for selection in selected_actions],
            "planned_action_targets": [
                {
                    "action_type": selection.action_type,
                    "channel_ref": selection.channel_ref,
                    "metadata": dict(selection.metadata),
                }
                for selection in selected_actions
            ],
        },
    )

    performed_actions: list[str] = []
    failed_actions: list[dict[str, Any]] = []

    if selected_actions:
        for selection in selected_actions:
            action_type = selection.action_type
            action_result = _dispatch_action(
                session,
                warmup_session=warmup_session,
                action_type=action_type,
                selected_channel_ref=selection.channel_ref,
                is_live=is_live,
                adapter=adapter,
                rng=rng,
                text_provider=text_provider,
                now=now,
            )
            if action_result is None:
                continue
            result, action_context = action_result
            if not result.is_ok:
                failed_actions.append(
                    _record_dispatch_action_failure(
                        session,
                        warmup_session,
                        action_type,
                        result,
                        action_context=action_context,
                        now=now,
                    )
                )
                continue
            counters_for_day[action_type] = counters_for_day.get(action_type, 0) + 1
            performed_actions.append(action_type)
            _record_dispatch_action_success(
                session,
                warmup_session,
                action_type=action_type,
                result=result,
                action_context=action_context,
                is_live=is_live,
                now=now,
            )
        if failed_actions:
            _record_failed_actions_in_counters(counters_for_day, failed_actions)
        if performed_actions:
            warmup_session.daily_counters_json = _persist_day_counters(
                warmup_session.daily_counters_json,
                warmup_session.current_day,
                counters_for_day,
            )
            warmup_session.last_micro_session_at = now
            warmup_session.last_step_at = now
            warmup_session.consecutive_failures = 0
            warmup_session.worker_id = worker_id
            warmup_session.status = WarmupStatus.ACTIVE
            if warmup_session.started_at is None:
                warmup_session.started_at = now
        if failed_actions and not performed_actions:
            warmup_session.daily_counters_json = _persist_day_counters(
                warmup_session.daily_counters_json,
                warmup_session.current_day,
                counters_for_day,
            )
            warmup_session.worker_id = worker_id
            retry_after_seconds = _max_retry_after_seconds(failed_actions)
            if retry_after_seconds is not None:
                retry_at = now + timedelta(seconds=retry_after_seconds)
                warmup_session.next_attempt_at = retry_at
                warmup_session.next_micro_session_at = retry_at
                warmup_session.next_step_at = retry_at
            error_summary = "; ".join(
                f"{a['action_type']}:{a.get('error_code', 'unknown')}" for a in failed_actions
            )
            breaker_tripped = handle_warmup_step_failure(
                session,
                warmup_session=warmup_session,
                error=error_summary,
                now=now,
                target_status=WarmupStatus.PAUSED_RISK,
            )
            if breaker_tripped:
                warmup_session.next_micro_session_at = None
                warmup_session.next_step_at = None
                write_warmup_event(
                    session,
                    warmup_session,
                    "micro_session_window_closed",
                    {
                        "day": warmup_session.current_day,
                        "performed_actions": performed_actions,
                        "failed_actions": failed_actions,
                        "counters": dict(counters_for_day),
                    },
                )
                session.flush()
                return True
            if retry_after_seconds is not None:
                warmup_session.updated_at = now
                write_warmup_event(
                    session,
                    warmup_session,
                    "micro_session_window_closed",
                    {
                        "day": warmup_session.current_day,
                        "performed_actions": performed_actions,
                        "failed_actions": failed_actions,
                        "counters": dict(counters_for_day),
                    },
                )
                session.flush()
                return True

    write_warmup_event(
        session,
        warmup_session,
        "micro_session_window_closed",
        {
            "day": warmup_session.current_day,
            "performed_actions": performed_actions,
            "failed_actions": failed_actions,
            "counters": dict(counters_for_day),
        },
    )

    day_complete = _is_day_complete(plan_for_day, counters_for_day)
    if day_complete:
        next_day = warmup_session.current_day + 1
        warmup_session.current_day = next_day
        write_warmup_event(
            session,
            warmup_session,
            "day_advanced",
            {"day": next_day, "execution_mode": warmup_session.execution_mode},
        )
        if next_day >= warmup_session.duration_days:
            _complete_dispatch_session(session, warmup_session, now=now)
            session.flush()
            return True
        _write_plan_adjustment_event_if_needed(session, warmup_session)
        warmup_session.next_micro_session_at = _next_day_first_window(
            now, warmup_session.timezone, rng=rng
        )
    else:
        warmup_session.next_micro_session_at = _schedule_within_day(
            now, warmup_session.timezone, rng=rng
        )

    warmup_session.next_step_at = warmup_session.next_micro_session_at
    warmup_session.updated_at = now
    session.flush()
    return True


def _skip_if_outside_cyclic_window(
    session: Session,
    warmup_session: WarmupSession,
    now: datetime,
) -> bool:
    status = cycle_window_status(warmup_session.cycle_config_json, now, warmup_session.timezone)
    if status is None or status.in_window:
        if status is not None:
            schedule_next_cycle(warmup_session, now=now)
        return False
    if status.completed:
        write_warmup_event(
            session,
            warmup_session,
            "cyclic.completed",
            {
                "current_cycle": status.current_cycle,
                "active_hours_total": status.active_hours_total,
            },
        )
        _complete_dispatch_session(session, warmup_session, now=now)
        session.flush()
        return True

    schedule_next_cycle(warmup_session, now=now)
    write_warmup_event(
        session,
        warmup_session,
        "task_skipped",
        {
            "reason": "cyclic_inactive_window",
            "current_cycle": status.current_cycle,
            "next_window_start": status.next_window_start.isoformat()
            if status.next_window_start
            else None,
        },
    )
    session.flush()
    return True


def _record_failed_actions_in_counters(
    counters_for_day: dict[str, int], failed_actions: list[dict[str, Any]]
) -> None:
    counters_for_day["failures"] = counters_for_day.get("failures", 0) + len(failed_actions)
    flood_waits = sum(1 for action in failed_actions if _is_flood_wait_failure(action))
    if flood_waits:
        counters_for_day["flood_waits"] = counters_for_day.get("flood_waits", 0) + flood_waits


def _is_flood_wait_failure(action: dict[str, Any]) -> bool:
    status = str(action.get("status") or "").lower()
    error_code = str(action.get("error_code") or "").lower()
    return status == "flood_wait" or error_code.startswith("flood_wait")


def _write_plan_adjustment_event_if_needed(session: Session, warmup_session: WarmupSession) -> None:
    adjustment = describe_next_day_adjustment(warmup_session)
    event_type = adjustment.event_type
    if event_type is None or not adjustment.is_active:
        return
    write_warmup_event(
        session,
        warmup_session,
        event_type,
        {
            "day": warmup_session.current_day,
            "multiplier": adjustment.multiplier,
            "reason": adjustment.reason,
            "action_types": list(adjustment.multipliers.keys()),
        },
    )
