from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    AccountRuntimeState,
    WarmupExecutionMode,
    WarmupSession,
    WarmupStatus,
    WarmupTaskRun,
    WarmupTaskRunStatus,
    new_id,
)
from app.modules.account_survival import events as survival_events
from app.modules.warmup.dispatch_results import _advance_account_to_pre_production
from app.modules.warmup.events import write_warmup_event
from app.modules.warmup.isolation import release_claim
from app.modules.warmup.pre_production import should_start_pre_production, start_pre_production
from app.modules.warmup.cold_soak import (
    advance_from_cold_soak,
    is_cold_soak_complete,
    record_cold_soak_in_progress,
)

DRY_RUN_TASK_TYPE = "dry_run_day"


def process_due_warmup_sessions(
    session: Session,
    *,
    workspace_id: str | None = None,
    now: datetime | None = None,
    worker_id: str,
    limit: int | None = None,
) -> int:
    timestamp = now or datetime.now(UTC)
    query = select(WarmupSession).where(
        WarmupSession.execution_mode == WarmupExecutionMode.DRY_RUN.value,
        (
            (
                WarmupSession.status.in_([WarmupStatus.SCHEDULED.value, WarmupStatus.ACTIVE.value])
                & (
                    (WarmupSession.next_step_at.is_(None))
                    | (WarmupSession.next_step_at <= timestamp)
                )
            )
            | (
                (WarmupSession.status == WarmupStatus.COLD_SOAK.value)
                & (
                    (WarmupSession.next_step_at.is_(None))
                    | (WarmupSession.next_step_at <= timestamp)
                    | (WarmupSession.cold_soak_until <= timestamp)
                )
            )
        ),
    )
    if workspace_id is not None:
        query = query.where(WarmupSession.workspace_id == workspace_id)
    query = query.order_by(WarmupSession.updated_at.asc()).limit(
        limit or settings.warmup_batch_limit
    )

    processed = 0
    for warmup_session in session.execute(query).scalars().all():
        if _process_one_due_session(session, warmup_session, now=timestamp, worker_id=worker_id):
            processed += 1
    session.commit()
    return processed


def handle_warmup_step_failure(
    session: Session,
    *,
    warmup_session: WarmupSession,
    error: str,
    max_failures: int | None = None,
    now: datetime | None = None,
    target_status: WarmupStatus = WarmupStatus.FAILED,
) -> bool:
    """Increment failure counter and trip circuit breaker if threshold reached.

    Returns True when the breaker trips (session status changed to
    *target_status*), False when the failure was recorded but the
    threshold is not yet reached.

    *target_status* allows callers to choose the terminal state:
    - ``WarmupStatus.FAILED`` (default) — hard failure used by dry-run worker.
    - ``WarmupStatus.PAUSED_RISK`` — soft pause used by live dispatch.
    """
    threshold = (
        max_failures if max_failures is not None else settings.warmup_max_consecutive_failures
    )
    timestamp = now or datetime.now(UTC)
    warmup_session.consecutive_failures += 1
    warmup_session.updated_at = timestamp
    if warmup_session.consecutive_failures >= threshold:
        warmup_session.status = target_status
        if target_status == WarmupStatus.PAUSED_RISK:
            warmup_session.paused_at = timestamp
        write_warmup_event(
            session,
            warmup_session,
            "circuit_breaker_triggered",
            {
                "error": error,
                "consecutive_failures": warmup_session.consecutive_failures,
                "threshold": threshold,
                "target_status": target_status.value
                if hasattr(target_status, "value")
                else str(target_status),
            },
        )
        session.flush()
        return True
    write_warmup_event(
        session,
        warmup_session,
        "task_skipped",
        {"reason": "worker_failure", "error": error},
    )
    session.flush()
    return False


def claim_account_runtime_lock(
    session: Session,
    *,
    account_id: str,
    owner: str,
    now: datetime,
) -> bool:
    result = cast(
        CursorResult[Any],
        session.execute(
            update(AccountRuntimeState)
            .where(
                AccountRuntimeState.account_id == account_id,
                AccountRuntimeState.lock_owner.is_(None),
            )
            .values(
                lock_owner=owner,
                lock_epoch=AccountRuntimeState.lock_epoch + 1,
                recovery_marker=f"warmup_lock_acquired:{owner}",
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        ),
    )
    return bool(result.rowcount)


def release_account_runtime_lock(
    session: Session,
    *,
    account_id: str,
    owner: str,
    now: datetime,
) -> None:
    session.execute(
        update(AccountRuntimeState)
        .where(
            AccountRuntimeState.account_id == account_id,
            AccountRuntimeState.lock_owner == owner,
        )
        .values(
            lock_owner=None,
            recovery_marker=f"warmup_lock_released:{owner}",
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )


def _process_one_due_session(
    session: Session,
    warmup_session: WarmupSession,
    *,
    now: datetime,
    worker_id: str,
) -> bool:
    owner = f"warmup:{worker_id}:{warmup_session.id}"
    runtime = session.get(AccountRuntimeState, warmup_session.account_id)
    if runtime is None or not claim_account_runtime_lock(
        session,
        account_id=warmup_session.account_id,
        owner=owner,
        now=now,
    ):
        write_warmup_event(
            session,
            warmup_session,
            "task_skipped",
            {"reason": "account_locked", "day": warmup_session.current_day},
        )
        session.flush()
        return False
    try:
        return _process_one_locked_session(session, warmup_session, now=now, worker_id=worker_id)
    finally:
        release_account_runtime_lock(
            session,
            account_id=warmup_session.account_id,
            owner=owner,
            now=now,
        )


def _process_one_locked_session(
    session: Session,
    warmup_session: WarmupSession,
    *,
    now: datetime,
    worker_id: str,
) -> bool:
    if warmup_session.status == WarmupStatus.COLD_SOAK.value:
        if not is_cold_soak_complete(warmup_session, now):
            record_cold_soak_in_progress(session, warmup_session, now)
            return False
        advance_from_cold_soak(session, warmup_session, now)

    existing = (
        session.execute(
            select(WarmupTaskRun).where(
                WarmupTaskRun.session_id == warmup_session.id,
                WarmupTaskRun.day == warmup_session.current_day,
                WarmupTaskRun.task_type == DRY_RUN_TASK_TYPE,
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        write_warmup_event(
            session,
            warmup_session,
            "task_skipped",
            {"reason": "duplicate_task_run", "day": warmup_session.current_day},
        )
        return False

    if warmup_session.current_day >= warmup_session.duration_days:
        _complete_session(session, warmup_session, now=now)
        return True

    task_run = WarmupTaskRun(
        id=new_id(),
        workspace_id=warmup_session.workspace_id,
        session_id=warmup_session.id,
        day=warmup_session.current_day,
        task_type=DRY_RUN_TASK_TYPE,
        status=WarmupTaskRunStatus.COMPLETED,
        worker_id=worker_id,
        metadata_json={"dry_run": True},
        started_at=now,
        completed_at=now,
    )
    session.add(task_run)

    next_day = warmup_session.current_day + 1
    warmup_session.current_day = next_day
    warmup_session.last_step_at = now
    warmup_session.worker_id = worker_id
    warmup_session.consecutive_failures = 0
    warmup_session.updated_at = now
    write_warmup_event(
        session,
        warmup_session,
        "task_executed",
        {"task_type": DRY_RUN_TASK_TYPE, "day": task_run.day, "dry_run": True},
    )
    write_warmup_event(session, warmup_session, "day_advanced", {"day": next_day})

    if next_day >= warmup_session.duration_days:
        _complete_session(session, warmup_session, now=now)
    else:
        warmup_session.status = WarmupStatus.ACTIVE
        if warmup_session.started_at is None:
            warmup_session.started_at = now
        warmup_session.next_step_at = now + timedelta(hours=warmup_session.cadence_hours)
    return True


def _complete_session(session: Session, warmup_session: WarmupSession, *, now: datetime) -> None:
    warmup_session.status = WarmupStatus.COMPLETED
    warmup_session.completed_at = now
    warmup_session.next_step_at = None
    warmup_session.updated_at = now
    write_warmup_event(session, warmup_session, "completed", {"day": warmup_session.current_day})
    _advance_account_to_pre_production(session, warmup_session, now)
    if should_start_pre_production(warmup_session):
        start_pre_production(
            session,
            account_id=warmup_session.account_id,
            workspace_id=warmup_session.workspace_id,
            source_warmup_session_id=warmup_session.id,
            source_warmup_session=warmup_session,
            now=now,
        )
    survival_events.on_warmup_completed(
        session,
        account_id=warmup_session.account_id,
        workspace_id=warmup_session.workspace_id,
        now=now,
    )
    if release_claim(
        session,
        account_id=warmup_session.account_id,
        held_by=f"warmup:{warmup_session.id}",
    ):
        write_warmup_event(
            session,
            warmup_session,
            "isolation_released",
            {"reason": "session_completed"},
        )
