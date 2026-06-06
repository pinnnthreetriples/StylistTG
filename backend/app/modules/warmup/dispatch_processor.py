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
from app.modules.warmup.events import write_warmup_event
from app.modules.warmup.worker import handle_warmup_step_failure

from .dispatch_actions import _dispatch_action
from .dispatch_context import _pause_if_blocked_by_safety_gate
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
    _select_actions_for_window,
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

    pending_actions = _select_actions_for_window(plan_for_day, counters_for_day, rng=rng)

    write_warmup_event(
        session,
        warmup_session,
        "micro_session_window_opened",
        {
            "day": warmup_session.current_day,
            "execution_mode": warmup_session.execution_mode,
            "planned_actions": list(pending_actions),
        },
    )

    performed_actions: list[str] = []
    failed_actions: list[dict[str, Any]] = []

    if pending_actions:
        for action_type in pending_actions:
            action_result = _dispatch_action(
                session,
                warmup_session=warmup_session,
                action_type=action_type,
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
