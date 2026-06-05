from __future__ import annotations

from typing import Any

from app.modules.warmup.contracts import (
    WarmupEventPageRead,
    WarmupEventRead,
    WarmupExecutionModeRead,
    WarmupIsolationClaimRead,
    WarmupIsolationStatusRead,
    WarmupPresetKindRead,
    WarmupSessionRead,
    WarmupSessionStatusRead,
    WarmupSessionSummaryRead,
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
        proxy_snapshot=warmup_session.proxy_snapshot_json,
        created_at=warmup_session.created_at,
        updated_at=warmup_session.updated_at,
        started_at=warmup_session.started_at,
        paused_at=warmup_session.paused_at,
        completed_at=warmup_session.completed_at,
        worker_id=warmup_session.worker_id,
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


_strategy_read = strategy_read


__all__ = [
    "_strategy_read",
    "event_page_read",
    "isolation_status_read",
    "session_read",
    "session_status_read",
    "session_summary",
    "strategy_read",
]
