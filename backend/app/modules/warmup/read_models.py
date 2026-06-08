from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.modules.warmup.contracts import (
    WarmupEventPageRead,
    WarmupEventRead,
    WarmupEventSeverityRead,
    WarmupExecutionModeRead,
    WarmupIsolationClaimRead,
    WarmupIsolationStatusRead,
    WarmupLiveEventAccountRead,
    WarmupLiveEventPageRead,
    WarmupLiveEventRead,
    WarmupPresetKindRead,
    WarmupSessionRead,
    WarmupSessionStatusRead,
    WarmupSessionSummaryRead,
    WarmupSessionTimerRead,
    WarmupStatusRead,
    WarmupStrategyRead,
)


def session_read(warmup_session: Any) -> WarmupSessionRead:
    return WarmupSessionRead(
        id=warmup_session.id,
        account_id=warmup_session.account_id,
        strategy_id=warmup_session.strategy_id,
        strategy_name=warmup_session.strategy.name,
        status=WarmupStatusRead(warmup_session.status),
        execution_mode=WarmupExecutionModeRead(warmup_session.execution_mode),
        duration_days=warmup_session.duration_days,
        current_day=warmup_session.current_day,
        cadence_hours=warmup_session.cadence_hours,
        timezone=warmup_session.timezone,
        next_step_at=warmup_session.next_step_at,
        last_step_at=warmup_session.last_step_at,
        next_attempt_at=warmup_session.next_attempt_at,
        next_micro_session_at=warmup_session.next_micro_session_at,
        last_micro_session_at=warmup_session.last_micro_session_at,
        cold_soak_until=warmup_session.cold_soak_until,
        consecutive_failures=warmup_session.consecutive_failures,
        daily_counters=warmup_session.daily_counters_json or {},
        trusted_peer_ids=warmup_session.trusted_peer_ids_json or [],
        disabled_actions=warmup_session.disabled_actions_json or [],
        proxy_snapshot=warmup_session.proxy_snapshot_json,
        created_at=warmup_session.created_at,
        updated_at=warmup_session.updated_at,
        started_at=warmup_session.started_at,
        paused_at=warmup_session.paused_at,
        completed_at=warmup_session.completed_at,
        worker_id=warmup_session.worker_id,
        cycle_config=warmup_session.cycle_config_json,
    )


def session_summary(warmup_session: Any) -> WarmupSessionSummaryRead:
    return WarmupSessionSummaryRead(
        id=warmup_session.id,
        account_id=warmup_session.account_id,
        account_label=warmup_session.account.external_ref,
        strategy_name=warmup_session.strategy.name,
        status=WarmupStatusRead(warmup_session.status),
        execution_mode=WarmupExecutionModeRead(warmup_session.execution_mode),
        duration_days=warmup_session.duration_days,
        current_day=warmup_session.current_day,
        cadence_hours=warmup_session.cadence_hours,
        next_step_at=warmup_session.next_step_at,
        next_micro_session_at=warmup_session.next_micro_session_at,
        cold_soak_until=warmup_session.cold_soak_until,
        updated_at=warmup_session.updated_at,
        cycle_config=warmup_session.cycle_config_json,
    )


def strategy_read(strategy: Any) -> WarmupStrategyRead:
    return WarmupStrategyRead(
        id=strategy.id,
        name=strategy.name,
        description=strategy.description,
        is_preset=strategy.is_preset,
        preset_kind=WarmupPresetKindRead(strategy.preset_kind),
        execution_mode=WarmupExecutionModeRead(strategy.execution_mode),
        duration_days=strategy.duration_days,
        daily_action_limits=strategy.daily_action_limits_json or {},
        session_window_config=strategy.session_window_config_json or {},
        ui_summary=strategy.ui_summary_json or {},
    )


def session_status_read(warmup_session: Any) -> WarmupSessionStatusRead:
    return WarmupSessionStatusRead(
        status=WarmupStatusRead(warmup_session.status),
        current_day=warmup_session.current_day,
        next_step_at=warmup_session.next_step_at,
        next_attempt_at=warmup_session.next_attempt_at,
        cold_soak_until=warmup_session.cold_soak_until,
    )


def session_timer_read(
    warmup_session: Any, *, now: datetime | None = None
) -> WarmupSessionTimerRead:
    timestamp = now or datetime.now(UTC)
    started_at = _timer_started_at(warmup_session)
    total_seconds = _timer_total_seconds(warmup_session)
    elapsed_seconds = _timer_elapsed_seconds(
        warmup_session,
        started_at=started_at,
        total_seconds=total_seconds,
        now=timestamp,
    )
    return WarmupSessionTimerRead(
        session_id=warmup_session.id,
        started_at=started_at,
        total_duration_seconds=total_seconds,
        elapsed_seconds=elapsed_seconds,
        status=_timer_status(warmup_session.status),
    )


def event_page_read(
    events: list[Any],
    *,
    total: int,
    page: int,
    limit: int,
) -> WarmupEventPageRead:
    return WarmupEventPageRead(
        items=[
            WarmupEventRead(
                id=item.id,
                event_type=item.event_type,
                severity=WarmupEventSeverityRead(getattr(item, "severity", "info")),
                payload=item.payload_json,
                created_at=item.created_at,
            )
            for item in events
        ],
        total=total,
        page=page,
        limit=limit,
    )


def isolation_status_read(claim: Any | None) -> WarmupIsolationStatusRead:
    if claim is None:
        return WarmupIsolationStatusRead(is_isolated=False, claim=None)
    return WarmupIsolationStatusRead(
        is_isolated=True,
        claim=WarmupIsolationClaimRead(
            account_id=claim.account_id,
            workspace_id=claim.workspace_id,
            held_by=claim.held_by,
            reason=claim.reason,
            acquired_at=claim.acquired_at,
        ),
    )


def live_event_read(event: Any) -> WarmupLiveEventRead:
    account = event.session.account
    label = str(account.external_ref)
    return WarmupLiveEventRead(
        id=event.id,
        event_id=event.id,
        session_id=event.session_id,
        account_id=event.session.account_id,
        account_label=label,
        phone_id=label,
        event_type=event.event_type,
        severity=WarmupEventSeverityRead(getattr(event, "severity", "info")),
        message=_event_message(event),
        payload=event.payload_json or {},
        occurred_at=event.created_at,
        created_at=event.created_at,
    )


def live_event_account_read(account: Any) -> WarmupLiveEventAccountRead:
    label = str(account.external_ref)
    return WarmupLiveEventAccountRead(
        account_id=account.id,
        account_label=label,
        phone_id=label,
    )


def live_event_page_read(
    events: list[Any],
    *,
    accounts: list[Any],
    total: int,
    limit: int,
) -> WarmupLiveEventPageRead:
    return WarmupLiveEventPageRead(
        items=[live_event_read(event) for event in events],
        total=total,
        limit=limit,
        next_cursor=events[-1].id if events else None,
        accounts=[live_event_account_read(account) for account in accounts],
    )


def _event_message(event: Any) -> str:
    payload = event.payload_json or {}
    action = payload.get("action_type")
    reason = payload.get("reason")
    if action and reason:
        return f"{event.event_type}: {action} ({reason})"
    if action:
        return f"{event.event_type}: {action}"
    if reason:
        return f"{event.event_type}: {reason}"
    return str(event.event_type)


def _timer_started_at(warmup_session: Any) -> datetime | None:
    cycle_config = warmup_session.cycle_config_json or {}
    started_at = cycle_config.get("started_at")
    if isinstance(started_at, str):
        try:
            return datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        except ValueError:
            pass
    return warmup_session.started_at or warmup_session.created_at


def _timer_total_seconds(warmup_session: Any) -> int:
    cycle_config = warmup_session.cycle_config_json or {}
    active_hours_total = cycle_config.get("active_hours_total")
    if isinstance(active_hours_total, int) and active_hours_total > 0:
        return active_hours_total * 3600
    duration_days = max(1, int(warmup_session.duration_days or 1))
    cadence_hours = max(1, int(warmup_session.cadence_hours or 1))
    return duration_days * cadence_hours * 3600


def _timer_elapsed_seconds(
    warmup_session: Any,
    *,
    started_at: datetime | None,
    total_seconds: int,
    now: datetime,
) -> int:
    if started_at is None:
        return 0
    reference = now
    if warmup_session.status in {"paused_risk", "paused_manual"}:
        reference = warmup_session.paused_at or warmup_session.updated_at or now
    elif warmup_session.status == "completed":
        reference = warmup_session.completed_at or warmup_session.updated_at or now
    elif warmup_session.status == "failed":
        reference = warmup_session.updated_at or now
    elapsed = int((_aware(reference) - _aware(started_at)).total_seconds())
    return max(0, min(total_seconds, elapsed))


def _timer_status(status: str) -> str:
    if status in {"active", "scheduled", "cold_soak", "validating"}:
        return "running"
    if status in {"paused_risk", "paused_manual"}:
        return "paused"
    if status == "completed":
        return "completed"
    return "stopped"


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


_strategy_read = strategy_read


__all__ = [
    "_strategy_read",
    "event_page_read",
    "isolation_status_read",
    "live_event_account_read",
    "live_event_page_read",
    "live_event_read",
    "session_read",
    "session_status_read",
    "session_summary",
    "session_timer_read",
    "strategy_read",
]
