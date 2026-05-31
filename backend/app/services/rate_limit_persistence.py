"""Persistent rate limiter fallback: flush Redis counters to Postgres, hydrate on recovery.

Redis is the hot cache; Postgres is the source of truth. This module provides:
- flush_redis_to_db: SCAN ratelimit keys -> bulk UPSERT into rate_limit_persistent_counters
- hydrate_redis_from_db: SELECT recent counters -> SET in Redis with remaining TTL

Key format (from NeuroCommentRateLimiter):
  neuro:{workspace_id}:limit:{scope_type}:{scope_id}:{limit_type}:{window_number}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import RateLimitPersistentCounter, new_id, utc_now
from app.modules.neuro_commenting.rate_limiter import (
    RATE_LIMIT_COUNTER_SCAN_PATTERN,
    build_rate_limit_counter_key,
    build_rate_limit_counter_metadata_key,
    parse_rate_limit_counter_key,
)


def _empty_scope_counts() -> dict[str, int]:
    return {}


SCOPE_KEY_WINDOW_SECONDS: dict[str, int] = {
    "comments_per_hour": 3600,
    "comments_per_day": 86400,
    "comments_per_minute": 60,
}

DEFAULT_WINDOW_SECONDS = 3600


@dataclass
class FlushReport:
    total_keys_scanned: int = 0
    upserted: int = 0
    expired_deleted: int = 0
    per_scope_counts: dict[str, int] = field(default_factory=_empty_scope_counts)


@dataclass
class HydrateReport:
    total_rows_loaded: int = 0
    keys_set: int = 0
    keys_skipped_warm: int = 0
    per_scope_counts: dict[str, int] = field(default_factory=_empty_scope_counts)


DEFAULT_SCOPE_KEYS = ("comments_per_minute", "comments_per_hour", "comments_per_day")


def _window_seconds_for_scope_key(scope_key: str) -> int:
    return SCOPE_KEY_WINDOW_SECONDS.get(scope_key, DEFAULT_WINDOW_SECONDS)


def _parse_limit_key(key: str) -> dict[str, Any] | None:
    """Parse a Redis rate limit key into components.

    Expected format: neuro:{workspace_id}:limit:{scope_type}:{scope_id}:{limit_type}:{window}
    """
    parsed = parse_rate_limit_counter_key(key)
    if parsed is None:
        return None
    return {
        "workspace_id": parsed.workspace_id,
        "scope_type": parsed.scope_type,
        "scope_id": parsed.scope_id,
        "scope_key": parsed.scope_key,
        "window_number": parsed.window_number,
    }


def _window_start_from_number(window_number: int, window_seconds: int) -> datetime:
    """Convert window number back to window_start datetime."""
    timestamp = window_number * window_seconds
    return datetime.fromtimestamp(timestamp, tz=UTC)


def redis_has_rate_limit_counters(redis: Any) -> bool:
    cursor: int | bytes | str = 0
    while True:
        cursor, keys = redis.scan(cursor=cursor, match=RATE_LIMIT_COUNTER_SCAN_PATTERN, count=100)
        if keys:
            return True
        if _scan_finished(cursor):
            return False


def _scan_finished(cursor: int | bytes | str) -> bool:
    if isinstance(cursor, bytes):
        cursor = cursor.decode()
    if isinstance(cursor, str):
        return cursor == "0"
    return cursor == 0


def flush_redis_to_db(
    session: Session,
    redis: Any,
    *,
    scope_keys: tuple[str, ...] | list[str] = DEFAULT_SCOPE_KEYS,
    now: datetime | None = None,
) -> FlushReport:
    """SCAN Redis ratelimit keys -> bulk UPSERT into rate_limit_persistent_counters."""
    report = FlushReport()
    current_time = now or utc_now()
    rows_to_upsert: list[dict[str, Any]] = []

    cursor: int | bytes = 0
    while True:
        cursor, keys = redis.scan(cursor=cursor, match=RATE_LIMIT_COUNTER_SCAN_PATTERN, count=500)
        for raw_key in keys:
            key = raw_key.decode() if isinstance(raw_key, bytes) else str(raw_key)
            parsed = _parse_limit_key(key)
            if parsed is None:
                continue
            if parsed["scope_key"] not in scope_keys:
                continue

            report.total_keys_scanned += 1
            raw_count = redis.get(key)
            if raw_count is None:
                continue
            count = int(raw_count)
            if count <= 0:
                continue

            window_seconds = _window_seconds_for_counter(redis, parsed)
            window_start = _window_start_from_number(parsed["window_number"], window_seconds)

            rows_to_upsert.append(
                {
                    "id": new_id(),
                    "workspace_id": parsed["workspace_id"],
                    "scope_type": parsed["scope_type"],
                    "scope_id": parsed["scope_id"],
                    "scope_key": parsed["scope_key"],
                    "window_seconds": window_seconds,
                    "window_start": window_start,
                    "count": count,
                    "updated_at": current_time,
                }
            )
            report.per_scope_counts[parsed["scope_key"]] = (
                report.per_scope_counts.get(parsed["scope_key"], 0) + 1
            )

        if _scan_finished(cursor):
            break

    if rows_to_upsert:
        _bulk_upsert(session, rows_to_upsert)
        report.upserted = len(rows_to_upsert)

    report.expired_deleted = _delete_expired(session, scope_keys, current_time)

    return report


def _bulk_upsert(session: Session, rows: list[dict[str, Any]]) -> None:
    """Upsert rows: update existing by unique key, insert new ones."""
    if not rows:
        return

    insert_factory = _insert_for_session(session)
    if insert_factory is not None:
        insert_stmt = insert_factory(RateLimitPersistentCounter).values(rows)
        statement = insert_stmt.on_conflict_do_update(
            index_elements=[
                "workspace_id",
                "scope_type",
                "scope_id",
                "scope_key",
                "window_start",
            ],
            set_={
                "count": insert_stmt.excluded.count,
                "window_seconds": insert_stmt.excluded.window_seconds,
                "updated_at": insert_stmt.excluded.updated_at,
            },
        )
        session.execute(statement)
        session.flush()
        return

    for row in rows:
        existing = (
            session.query(RateLimitPersistentCounter)
            .filter_by(
                workspace_id=row["workspace_id"],
                scope_type=row["scope_type"],
                scope_id=row["scope_id"],
                scope_key=row["scope_key"],
                window_start=row["window_start"],
            )
            .first()
        )
        if existing is not None:
            existing.count = row["count"]
            existing.window_seconds = row["window_seconds"]
            existing.updated_at = row["updated_at"]
        else:
            session.add(RateLimitPersistentCounter(**row))


def _insert_for_session(session: Session):
    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        return pg_insert
    if dialect_name == "sqlite":
        return sqlite_insert
    return None


def _window_seconds_for_counter(redis: Any, parsed: dict[str, Any]) -> int:
    metadata_key = build_rate_limit_counter_metadata_key(
        workspace_id=parsed["workspace_id"],
        scope_type=parsed["scope_type"],
        scope_id=parsed["scope_id"],
        scope_key=parsed["scope_key"],
        window_number=parsed["window_number"],
    )
    raw_window_seconds = redis.get(metadata_key)
    if raw_window_seconds is not None:
        try:
            if isinstance(raw_window_seconds, bytes):
                raw_window_seconds = raw_window_seconds.decode()
            window_seconds = int(raw_window_seconds)
            if window_seconds > 0:
                return window_seconds
        except ValueError:
            # Corrupt metadata value — fall back to the scope-key default below.
            pass
    return _window_seconds_for_scope_key(parsed["scope_key"])


def _delete_expired(
    session: Session,
    scope_keys: tuple[str, ...] | list[str],
    now: datetime,
) -> int:
    """Delete rows older than 2x the scope window (built-in retention)."""
    total_deleted = 0
    for scope_key in scope_keys:
        window_seconds = _window_seconds_for_scope_key(scope_key)
        cutoff = now - timedelta(seconds=window_seconds * 2)
        result = cast(
            Any,
            session.execute(
                delete(RateLimitPersistentCounter).where(
                    RateLimitPersistentCounter.scope_key == scope_key,
                    RateLimitPersistentCounter.window_start < cutoff,
                )
            ),
        )
        total_deleted += int(result.rowcount or 0)
    return total_deleted


def hydrate_redis_from_db(
    session: Session,
    redis: Any,
    *,
    since: datetime | None = None,
    now: datetime | None = None,
) -> HydrateReport:
    """SELECT recent counters from DB -> SET in Redis with TTL = remaining window seconds."""
    report = HydrateReport()
    current_time = now or utc_now()

    query = session.query(RateLimitPersistentCounter)
    if since is not None:
        query = query.filter(RateLimitPersistentCounter.window_start >= since)
    else:
        min_cutoff = current_time - timedelta(days=1)
        query = query.filter(RateLimitPersistentCounter.window_start >= min_cutoff)

    rows = query.all()
    report.total_rows_loaded = len(rows)

    for row in rows:
        window_seconds = int(row.window_seconds or _window_seconds_for_scope_key(row.scope_key))
        ws = row.window_start
        if ws.tzinfo is None:
            ws = ws.replace(tzinfo=UTC)
        window_end = ws + timedelta(seconds=window_seconds)
        remaining_seconds = int((window_end - current_time).total_seconds())

        if remaining_seconds <= 0:
            continue

        window_number = int(ws.timestamp() // window_seconds)
        redis_key = build_rate_limit_counter_key(
            workspace_id=row.workspace_id,
            scope_type=row.scope_type,
            scope_id=row.scope_id,
            scope_key=row.scope_key,
            window_number=window_number,
        )

        existing = redis.get(redis_key)
        if existing is not None:
            report.keys_skipped_warm += 1
            continue

        redis.set(redis_key, str(row.count), ex=remaining_seconds)
        metadata_key = build_rate_limit_counter_metadata_key(
            workspace_id=row.workspace_id,
            scope_type=row.scope_type,
            scope_id=row.scope_id,
            scope_key=row.scope_key,
            window_number=window_number,
        )
        redis.set(metadata_key, str(window_seconds), ex=remaining_seconds)
        report.keys_set += 1
        report.per_scope_counts[row.scope_key] = report.per_scope_counts.get(row.scope_key, 0) + 1

    return report


__all__ = [
    "FlushReport",
    "HydrateReport",
    "flush_redis_to_db",
    "hydrate_redis_from_db",
    "redis_has_rate_limit_counters",
]
