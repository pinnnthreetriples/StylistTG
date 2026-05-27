from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    AccountQuarantine,
    AccountStatusObservation,
    CrossModuleLoadBucket,
    NeuroCommentEvent,
)

_QUARANTINE_ARCHIVE_DAYS = 365


@dataclass(frozen=True)
class RetentionReport:
    events_deleted: int
    observations_deleted: int
    load_buckets_deleted: int
    quarantines_archived: int


def run_retention_tick(session: Session, *, now: datetime) -> RetentionReport:
    events_deleted = _delete_older_than(
        session,
        NeuroCommentEvent,
        NeuroCommentEvent.created_at,
        now - timedelta(days=settings.safety_retention_days_default),
    )
    observations_deleted = _delete_older_than(
        session,
        AccountStatusObservation,
        AccountStatusObservation.observed_at,
        now - timedelta(days=settings.safety_retention_days_observations),
    )
    load_buckets_deleted = _delete_older_than(
        session,
        CrossModuleLoadBucket,
        CrossModuleLoadBucket.bucket_start,
        now - timedelta(days=settings.safety_retention_days_load_buckets),
    )
    quarantines_archived = _delete_older_than(
        session,
        AccountQuarantine,
        AccountQuarantine.released_at,
        now - timedelta(days=_QUARANTINE_ARCHIVE_DAYS),
        require_released=True,
    )
    return RetentionReport(
        events_deleted=events_deleted,
        observations_deleted=observations_deleted,
        load_buckets_deleted=load_buckets_deleted,
        quarantines_archived=quarantines_archived,
    )


def _delete_older_than(
    session: Session,
    model: type[Any],
    column: Any,
    cutoff: datetime,
    *,
    require_released: bool = False,
) -> int:
    statement = delete(model).where(column < cutoff)
    if require_released:
        statement = statement.where(AccountQuarantine.released_at.is_not(None))
    result = cast(CursorResult[Any], session.execute(statement))
    return int(result.rowcount or 0)


__all__ = ["RetentionReport", "run_retention_tick"]
