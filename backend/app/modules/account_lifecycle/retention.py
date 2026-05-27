from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.modules.account_lifecycle import repository

_QUARANTINE_ARCHIVE_DAYS = 365


@dataclass(frozen=True)
class RetentionReport:
    events_deleted: int
    observations_deleted: int
    load_buckets_deleted: int
    quarantines_archived: int


def run_retention_tick(session: Session, *, now: datetime) -> RetentionReport:
    events_deleted = repository.delete_neuro_comment_events_before(
        session,
        cutoff=now - timedelta(days=settings.safety_retention_days_default),
    )
    observations_deleted = repository.delete_status_observations_before(
        session,
        cutoff=now - timedelta(days=settings.safety_retention_days_observations),
    )
    load_buckets_deleted = repository.delete_load_buckets_before(
        session,
        cutoff=now - timedelta(days=settings.safety_retention_days_load_buckets),
    )
    quarantines_archived = repository.archive_released_quarantines_before(
        session,
        cutoff=now - timedelta(days=_QUARANTINE_ARCHIVE_DAYS),
    )
    return RetentionReport(
        events_deleted=events_deleted,
        observations_deleted=observations_deleted,
        load_buckets_deleted=load_buckets_deleted,
        quarantines_archived=quarantines_archived,
    )


__all__ = ["RetentionReport", "run_retention_tick"]
