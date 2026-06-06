from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import WarmupEvent, WarmupExecutionMode, WarmupSession, WarmupStatus
from app.modules.warmup.events import write_warmup_event

_IN_PROGRESS_EVENT_MIN_INTERVAL = timedelta(hours=1)


def compute_cold_soak_window(strategy: Any, now: datetime) -> datetime:
    del strategy
    min_seconds = settings.warmup_cold_soak_min_hours * 3600
    max_seconds = settings.warmup_cold_soak_max_hours * 3600
    return now + timedelta(seconds=random.randint(min_seconds, max_seconds))


def is_cold_soak_complete(warmup_session: WarmupSession, now: datetime) -> bool:
    if warmup_session.status != WarmupStatus.COLD_SOAK.value:
        return True
    if warmup_session.cold_soak_until is None:
        return True
    return warmup_session.cold_soak_until <= now


def advance_from_cold_soak(session: Session, warmup_session: WarmupSession, now: datetime) -> bool:
    if warmup_session.status != WarmupStatus.COLD_SOAK.value:
        return False
    warmup_session.status = WarmupStatus.SCHEDULED
    warmup_session.next_step_at = now
    if warmup_session.execution_mode != WarmupExecutionMode.DRY_RUN.value:
        warmup_session.next_micro_session_at = now
    warmup_session.updated_at = now
    event = write_warmup_event(
        session,
        warmup_session,
        "cold_soak_completed",
        {"transitioned_at": now.isoformat()},
    )
    event.created_at = now
    session.flush()
    return True


def record_cold_soak_in_progress(
    session: Session, warmup_session: WarmupSession, now: datetime
) -> None:
    if warmup_session.cold_soak_until is not None:
        warmup_session.next_step_at = warmup_session.cold_soak_until
        if warmup_session.execution_mode != WarmupExecutionMode.DRY_RUN.value:
            warmup_session.next_micro_session_at = warmup_session.cold_soak_until
    warmup_session.updated_at = now
    if _should_write_in_progress_event(session, warmup_session, now):
        event = write_warmup_event(
            session,
            warmup_session,
            "cold_soak_in_progress",
            {
                "until": warmup_session.cold_soak_until.isoformat()
                if warmup_session.cold_soak_until
                else None,
            },
        )
        event.created_at = now
    session.flush()


def _should_write_in_progress_event(
    session: Session, warmup_session: WarmupSession, now: datetime
) -> bool:
    threshold = now - _IN_PROGRESS_EVENT_MIN_INTERVAL
    recent = session.execute(
        select(  # nosemgrep: missing-workspace-id-filter-projection - workspace_id predicate is below.
            WarmupEvent.id
        )
        .where(
            WarmupEvent.workspace_id == warmup_session.workspace_id,
            WarmupEvent.session_id == warmup_session.id,
            WarmupEvent.event_type == "cold_soak_in_progress",
            WarmupEvent.created_at >= threshold,
        )
        .limit(1)
    ).first()
    return recent is None
