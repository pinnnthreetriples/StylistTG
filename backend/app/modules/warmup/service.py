from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from redis import Redis
from sqlalchemy.orm import Session

from app.config import settings
from app.job_queue.rq import enqueue_warmup_dispatch_tick, enqueue_warmup_due_sessions
from app.models import WarmupExecutionMode, WarmupSession, WarmupStatus, new_id
from app.modules.warmup import repository
from app.modules.warmup.contracts import (
    WarmupEventPageRead,
    WarmupEventRead,
    WarmupExecutionModeRead,
    WarmupIsolationClaimRead,
    WarmupIsolationStatusRead,
    WarmupPresetKindRead,
    WarmupReadinessRead,
    WarmupSessionPageRead,
    WarmupSessionRead,
    WarmupSessionStatusRead,
    WarmupSessionSummaryRead,
    WarmupStatusRead,
    WarmupStrategyRead,
    WarmupValidateRead,
)
from app.modules.warmup.errors import (
    WarmupError,
    WarmupIsolationConflictError,
    WarmupQueueUnavailableError,
)
from app.modules.warmup.events import write_warmup_event
from app.modules.warmup.isolation import acquire_claim, get_claim, release_claim
from app.modules.warmup.policies import (
    can_create_warmup_session,
    is_live_warmup_mode,
    is_warmup_active_status,
    validate_session_status_transition,
)
from app.modules.warmup.policies import warmup_operation_policy as _warmup_operation_policy
from app.modules.warmup.readiness import validate_warmup_readiness


get_warmup_session = repository.get_warmup_session
list_warmup_sessions = repository.list_warmup_sessions
list_warmup_events = repository.list_warmup_events
active_warmup_for_account = repository.active_warmup_for_account
batch_active_warmups_for_accounts = repository.batch_active_warmups_for_accounts


def get_warmup_readiness(session: Session, *, workspace_id: str) -> WarmupReadinessRead:
    return WarmupReadinessRead(
        workers_enabled=settings.warmup_workers_enabled,
        dry_run=settings.warmup_dry_run,
        redis_connected=_redis_connected(),
        database_connected=True,
        active_sessions=repository.count_active_sessions(session, workspace_id=workspace_id),
        strategies_available=repository.count_available_strategies(
            session, workspace_id=workspace_id
        ),
    )


def validate_warmup(
    session: Session,
    *,
    account_id: str,
    strategy_id: str,
    workspace_id: str,
) -> WarmupValidateRead:
    return validate_warmup_readiness(
        session,
        account_id=account_id,
        strategy_id=strategy_id,
        workspace_id=workspace_id,
    )


def list_warmup_strategies(session: Session, *, workspace_id: str) -> list[WarmupStrategyRead]:
    return [
        _strategy_read(strategy)
        for strategy in repository.list_available_strategies(session, workspace_id=workspace_id)
    ]


def create_warmup_session(
    session: Session,
    *,
    account_id: str,
    strategy_id: str,
    workspace_id: str,
    now: datetime | None = None,
) -> WarmupSession:
    readiness = validate_warmup_readiness(
        session,
        account_id=account_id,
        strategy_id=strategy_id,
        workspace_id=workspace_id,
    )
    can_create_warmup_session(readiness.blocking_reasons)

    timestamp = now or datetime.now(UTC)
    strategy = repository.get_strategy(session, strategy_id=strategy_id)
    execution_mode = (
        strategy.execution_mode if strategy is not None else WarmupExecutionMode.DRY_RUN.value
    )
    duration_days = (
        strategy.duration_days if strategy is not None else settings.warmup_default_duration_days
    )
    proxy_snapshot = _build_proxy_snapshot(session, account_id=account_id)

    warmup_session = WarmupSession(
        id=new_id(),
        workspace_id=workspace_id,
        account_id=account_id,
        strategy_id=strategy_id,
        status=WarmupStatus.SCHEDULED,
        current_day=0,
        cadence_hours=settings.warmup_default_cadence_hours,
        next_step_at=timestamp,
        next_micro_session_at=timestamp if is_live_warmup_mode(execution_mode) else None,
        execution_mode=execution_mode,
        duration_days=duration_days,
        proxy_snapshot_json=proxy_snapshot,
    )
    session.add(warmup_session)
    session.flush()
    write_warmup_event(
        session,
        warmup_session,
        "session_created",
        {
            "status": WarmupStatus.SCHEDULED.value,
            "strategy_id": strategy_id,
            "execution_mode": execution_mode,
            "duration_days": duration_days,
            "proxy_snapshot": proxy_snapshot,
        },
    )
    if is_live_warmup_mode(execution_mode):
        owner = f"warmup:{warmup_session.id}"
        claim_acquired = acquire_claim(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
            held_by=owner,
            reason=f"warmup execution_mode={execution_mode}",
            now=timestamp,
        )
        if not claim_acquired:
            raise WarmupIsolationConflictError()
        write_warmup_event(
            session,
            warmup_session,
            "isolation_claimed",
            {"held_by": owner, "execution_mode": execution_mode},
        )
    return warmup_session


def create_warmup_session_use_case(
    session: Session,
    *,
    account_id: str,
    strategy_id: str,
    workspace_id: str,
) -> WarmupSessionRead:
    warmup_session = create_warmup_session(
        session,
        account_id=account_id,
        strategy_id=strategy_id,
        workspace_id=workspace_id,
    )
    session.commit()
    session.refresh(warmup_session)
    enqueue_ok = True
    if settings.warmup_workers_enabled:
        enqueue_ok = (
            enqueue_warmup_due_sessions()
            if warmup_session.execution_mode == WarmupExecutionMode.DRY_RUN.value
            else enqueue_warmup_dispatch_tick()
        )
    if enqueue_ok is False:
        warmup_session.status = WarmupStatus.FAILED
        write_warmup_event(session, warmup_session, "queue_enqueue_failed", {})
        release_claim(
            session,
            account_id=warmup_session.account_id,
            held_by=f"warmup:{warmup_session.id}",
        )
        session.commit()
        raise WarmupQueueUnavailableError()
    return session_read(warmup_session)


def list_warmup_sessions_page(
    session: Session,
    *,
    workspace_id: str,
    statuses: list[str] | None,
    page: int,
    limit: int,
) -> WarmupSessionPageRead:
    items, total = repository.list_warmup_sessions(
        session,
        workspace_id=workspace_id,
        statuses=statuses,
        page=page,
        limit=limit,
    )
    return WarmupSessionPageRead(
        items=[session_summary(item) for item in items],
        total=total,
        page=page,
        limit=limit,
    )


def get_warmup_session_detail(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
) -> WarmupSessionRead:
    return session_read(
        repository.get_warmup_session(session, session_id=session_id, workspace_id=workspace_id)
    )


def get_warmup_session_status(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
) -> WarmupSessionStatusRead:
    warmup_session = repository.get_warmup_session(
        session, session_id=session_id, workspace_id=workspace_id
    )
    return WarmupSessionStatusRead(
        status=WarmupStatusRead(warmup_session.status),
        current_day=warmup_session.current_day,
        next_step_at=warmup_session.next_step_at,
        next_attempt_at=warmup_session.next_attempt_at,
    )


def pause_warmup_session(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
    reason: str,
    now: datetime | None = None,
) -> WarmupSession:
    warmup_session = repository.get_warmup_session(
        session, session_id=session_id, workspace_id=workspace_id
    )
    validate_session_status_transition(action="pause", current_status=warmup_session.status)
    timestamp = now or datetime.now(UTC)
    warmup_session.status = WarmupStatus.PAUSED_MANUAL
    warmup_session.paused_at = timestamp
    warmup_session.updated_at = timestamp
    write_warmup_event(session, warmup_session, "paused", {"reason": reason})
    return warmup_session


def pause_warmup_session_use_case(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
    reason: str,
) -> WarmupSessionRead:
    warmup_session = pause_warmup_session(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        reason=reason,
    )
    session.commit()
    session.refresh(warmup_session)
    return session_read(warmup_session)


def resume_warmup_session(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
    now: datetime | None = None,
) -> WarmupSession:
    warmup_session = repository.get_warmup_session(
        session, session_id=session_id, workspace_id=workspace_id
    )
    timestamp = now or datetime.now(UTC)
    validate_session_status_transition(
        action="resume",
        current_status=warmup_session.status,
        next_attempt_at=warmup_session.next_attempt_at,
        now=timestamp,
    )
    warmup_session.status = WarmupStatus.SCHEDULED
    warmup_session.paused_at = None
    warmup_session.consecutive_failures = 0
    warmup_session.updated_at = timestamp
    write_warmup_event(session, warmup_session, "resumed", {})
    return warmup_session


def resume_warmup_session_use_case(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
) -> WarmupSessionRead:
    warmup_session = resume_warmup_session(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
    )
    session.commit()
    session.refresh(warmup_session)
    return session_read(warmup_session)


def delete_warmup_session(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
) -> None:
    warmup_session = repository.get_warmup_session(
        session, session_id=session_id, workspace_id=workspace_id
    )
    release_claim(
        session,
        account_id=warmup_session.account_id,
        held_by=f"warmup:{warmup_session.id}",
    )
    session.delete(warmup_session)


def delete_warmup_session_use_case(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
) -> None:
    delete_warmup_session(session, session_id=session_id, workspace_id=workspace_id)
    session.commit()


def list_warmup_session_events_page(
    session: Session,
    *,
    session_id: str,
    workspace_id: str,
    page: int,
    limit: int,
) -> WarmupEventPageRead:
    items, total = repository.list_warmup_events(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        page=page,
        limit=limit,
    )
    return WarmupEventPageRead(
        items=[
            WarmupEventRead(
                id=item.id,
                event_type=item.event_type,
                payload=item.payload_json,
                created_at=item.created_at,
            )
            for item in items
        ],
        total=total,
        page=page,
        limit=limit,
    )


def get_warmup_isolation_status(session: Session, *, account_id: str) -> WarmupIsolationStatusRead:
    claim = get_claim(session, account_id=account_id)
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


def warmup_operation_policy(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    operation: str,
) -> dict[str, Any]:
    return _warmup_operation_policy(
        warmup_session=repository.active_warmup_for_account(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
        ),
        operation=operation,
    )


def session_read(warmup_session: WarmupSession) -> WarmupSessionRead:
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


def session_summary(warmup_session: WarmupSession) -> WarmupSessionSummaryRead:
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
        updated_at=warmup_session.updated_at,
    )


def _strategy_read(strategy: Any) -> WarmupStrategyRead:
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


def _build_proxy_snapshot(session: Session, *, account_id: str) -> dict[str, Any] | None:
    """Return the safe AccountProxy snapshot captured at session creation."""
    proxy = repository.get_account_proxy_snapshot_source(session, account_id=account_id)
    if proxy is None:
        return None
    return {
        "proxy_type": proxy.proxy_type,
        "proxy_category": proxy.proxy_category,
        "host": proxy.host,
        "port": proxy.port,
        "status": proxy.status,
        "last_checked_at": (
            proxy.last_checked_at.isoformat() if proxy.last_checked_at is not None else None
        ),
    }


def _redis_connected() -> bool:
    try:
        client = cast(
            Redis, cast(Any, Redis).from_url(settings.redis_url, socket_connect_timeout=0.2)
        )
        try:
            return bool(cast(Any, client).ping())
        finally:
            client.close()
    except Exception:
        return False


def warmup_error_to_status_code(exc: WarmupError, default: int) -> int:
    return exc.status_code or default


__all__ = [
    "active_warmup_for_account",
    "batch_active_warmups_for_accounts",
    "create_warmup_session",
    "create_warmup_session_use_case",
    "delete_warmup_session",
    "delete_warmup_session_use_case",
    "get_warmup_isolation_status",
    "get_warmup_readiness",
    "get_warmup_session",
    "get_warmup_session_detail",
    "get_warmup_session_status",
    "is_warmup_active_status",
    "list_warmup_events",
    "list_warmup_session_events_page",
    "list_warmup_sessions",
    "list_warmup_sessions_page",
    "list_warmup_strategies",
    "pause_warmup_session",
    "pause_warmup_session_use_case",
    "resume_warmup_session",
    "resume_warmup_session_use_case",
    "session_read",
    "session_summary",
    "validate_warmup",
    "warmup_error_to_status_code",
    "warmup_operation_policy",
    "write_warmup_event",
]
