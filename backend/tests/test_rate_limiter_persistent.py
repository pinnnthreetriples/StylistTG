"""Tests for rate_limit_persistence: flush Redis to DB and hydrate DB to Redis."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import perf_counter

from freezegun import freeze_time

from app.config import Settings
from app.models import RateLimitPersistentCounter, new_id
from app.services.rate_limit_persistence import (
    _parse_limit_key,
    _window_start_from_number,
    flush_redis_to_db,
    hydrate_redis_from_db,
)
from app.services.scheduler import RATE_LIMIT_FLUSH_TICK_SECONDS, scheduler_report

_FROZEN_NOW = "2026-05-21T12:00:00+00:00"
_FROZEN_DT = datetime(2026, 5, 21, 12, 0, 0, tzinfo=UTC)

_WORKSPACE_ID = "ws-00000000-0000-4000-8000-000000000001"
_ACCOUNT_ID = "acc-0000-0000-0000-0000-000000000001"
_CAMPAIGN_ID = "cmp-0000-0000-0000-0000-000000000001"


class FakeRedis:
    """Minimal fake Redis for testing scan/get/set operations."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, int | None]] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._store[key] = (value, ex)
        return True

    def get(self, key: str) -> bytes | None:
        if key in self._store:
            return self._store[key][0].encode() if isinstance(self._store[key][0], str) else None
        return None

    def scan(self, cursor: int = 0, match: str = "*", count: int = 100) -> tuple[int, list[bytes]]:
        keys = [k.encode() for k in self._store if self._matches(k, match)]
        return (0, keys)

    def dbsize(self) -> int:
        return len(self._store)

    def flushall(self) -> None:
        self._store.clear()

    def ttl(self, key: str) -> int:
        if key in self._store:
            ex = self._store[key][1]
            return ex if ex is not None else -1
        return -2

    def _matches(self, key: str, pattern: str) -> bool:
        import fnmatch

        return fnmatch.fnmatch(key, pattern)


def _make_redis_key(
    workspace_id: str,
    scope_type: str,
    scope_id: str,
    scope_key: str,
    window_number: int,
) -> str:
    return f"neuro:{workspace_id}:limit:{scope_type}:{scope_id}:{scope_key}:{window_number}"


def test_scheduler_report_registers_rate_limit_flush_tick():
    report = scheduler_report(Settings(_env_file=None))

    assert report.planned_ticks["rate_limit_flush"] == RATE_LIMIT_FLUSH_TICK_SECONDS


@freeze_time(_FROZEN_NOW)
def test_flush_redis_counter_to_db(db_session):
    """Flush: Redis counter becomes a DB row with count and window_start."""
    redis = FakeRedis()
    window_seconds = 3600
    window_number = int(_FROZEN_DT.timestamp() // window_seconds)
    key = _make_redis_key(_WORKSPACE_ID, "account", _ACCOUNT_ID, "comments_per_hour", window_number)
    redis.set(key, "5")

    report = flush_redis_to_db(db_session, redis, now=_FROZEN_DT)
    db_session.commit()

    assert report.upserted == 1
    assert report.per_scope_counts.get("comments_per_hour") == 1

    row = (
        db_session.query(RateLimitPersistentCounter)
        .filter_by(
            workspace_id=_WORKSPACE_ID,
            scope_type="account",
            scope_id=_ACCOUNT_ID,
            scope_key="comments_per_hour",
        )
        .first()
    )
    assert row is not None
    assert row.count == 5
    expected_window_start = _window_start_from_number(window_number, window_seconds)
    stored_ws = row.window_start
    if stored_ws.tzinfo is None:
        stored_ws = stored_ws.replace(tzinfo=UTC)
    assert stored_ws == expected_window_start


@freeze_time(_FROZEN_NOW)
def test_flush_idempotent_no_doubling(db_session):
    """Flush idempotent: running twice doesn't double counts."""
    redis = FakeRedis()
    window_seconds = 3600
    window_number = int(_FROZEN_DT.timestamp() // window_seconds)
    key = _make_redis_key(
        _WORKSPACE_ID, "campaign", _CAMPAIGN_ID, "comments_per_hour", window_number
    )
    redis.set(key, "10")

    flush_redis_to_db(db_session, redis, now=_FROZEN_DT)
    db_session.commit()

    flush_redis_to_db(db_session, redis, now=_FROZEN_DT)
    db_session.commit()

    rows = (
        db_session.query(RateLimitPersistentCounter)
        .filter_by(
            workspace_id=_WORKSPACE_ID,
            scope_type="campaign",
            scope_id=_CAMPAIGN_ID,
            scope_key="comments_per_hour",
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].count == 10


@freeze_time(_FROZEN_NOW)
def test_hydrate_empty_redis_from_db(db_session):
    """Hydrate in empty Redis: DB counters become Redis keys with TTL."""
    redis = FakeRedis()
    window_seconds = 3600
    window_number = int(_FROZEN_DT.timestamp() // window_seconds)
    window_start = _window_start_from_number(window_number, window_seconds)

    for i in range(3):
        db_session.add(
            RateLimitPersistentCounter(
                id=new_id(),
                workspace_id=_WORKSPACE_ID,
                scope_type="account",
                scope_id=f"acc-{i:036d}",
                scope_key="comments_per_hour",
                window_start=window_start,
                count=i + 1,
                updated_at=_FROZEN_DT,
            )
        )
    db_session.commit()

    report = hydrate_redis_from_db(db_session, redis, now=_FROZEN_DT)

    assert report.keys_set == 3
    assert report.keys_skipped_warm == 0

    for i in range(3):
        expected_key = _make_redis_key(
            _WORKSPACE_ID, "account", f"acc-{i:036d}", "comments_per_hour", window_number
        )
        assert redis.get(expected_key) is not None
        ttl = redis.ttl(expected_key)
        assert 0 < ttl <= window_seconds


@freeze_time(_FROZEN_NOW)
def test_hydrate_skip_warm_redis(db_session):
    """Hydrate skip warm Redis: key already SET in Redis is not overwritten."""
    redis = FakeRedis()
    window_seconds = 3600
    window_number = int(_FROZEN_DT.timestamp() // window_seconds)
    window_start = _window_start_from_number(window_number, window_seconds)

    redis_key = _make_redis_key(
        _WORKSPACE_ID, "account", _ACCOUNT_ID, "comments_per_hour", window_number
    )
    redis.set(redis_key, "99", ex=1800)

    db_session.add(
        RateLimitPersistentCounter(
            id=new_id(),
            workspace_id=_WORKSPACE_ID,
            scope_type="account",
            scope_id=_ACCOUNT_ID,
            scope_key="comments_per_hour",
            window_start=window_start,
            count=5,
            updated_at=_FROZEN_DT,
        )
    )
    db_session.commit()

    report = hydrate_redis_from_db(db_session, redis, now=_FROZEN_DT)

    assert report.keys_skipped_warm == 1
    assert report.keys_set == 0
    assert redis.get(redis_key) == b"99"


@freeze_time(_FROZEN_NOW)
def test_flushall_then_hydrate_recovery(db_session):
    """Simulate FLUSHALL: setup, flush, clear Redis, hydrate, counters restored."""
    redis = FakeRedis()
    window_seconds = 3600
    window_number = int(_FROZEN_DT.timestamp() // window_seconds)
    key = _make_redis_key(_WORKSPACE_ID, "account", _ACCOUNT_ID, "comments_per_hour", window_number)
    redis.set(key, "7")

    flush_redis_to_db(db_session, redis, now=_FROZEN_DT)
    db_session.commit()

    redis.flushall()
    assert redis.dbsize() == 0

    report = hydrate_redis_from_db(db_session, redis, now=_FROZEN_DT)

    assert report.keys_set == 1
    restored_value = redis.get(key)
    assert restored_value == b"7"


@freeze_time(_FROZEN_NOW)
def test_retention_deletes_expired_rows(db_session):
    """Retention: row older than 2x scope_window is deleted during flush."""
    redis = FakeRedis()
    window_seconds = 3600
    old_window_start = _FROZEN_DT - timedelta(seconds=window_seconds * 3)

    db_session.add(
        RateLimitPersistentCounter(
            id=new_id(),
            workspace_id=_WORKSPACE_ID,
            scope_type="account",
            scope_id=_ACCOUNT_ID,
            scope_key="comments_per_hour",
            window_start=old_window_start,
            count=99,
            updated_at=old_window_start,
        )
    )
    db_session.commit()

    report = flush_redis_to_db(db_session, redis, now=_FROZEN_DT)
    db_session.commit()

    assert report.expired_deleted == 1

    remaining = (
        db_session.query(RateLimitPersistentCounter)
        .filter_by(
            workspace_id=_WORKSPACE_ID,
            scope_type="account",
            scope_id=_ACCOUNT_ID,
        )
        .all()
    )
    assert len(remaining) == 0


def test_parse_limit_key_valid():
    """Verify _parse_limit_key handles valid and invalid keys."""
    key = "neuro:ws1:limit:account:acc1:comments_per_hour:12345"
    parsed = _parse_limit_key(key)
    assert parsed is not None
    assert parsed["workspace_id"] == "ws1"
    assert parsed["scope_type"] == "account"
    assert parsed["scope_id"] == "acc1"
    assert parsed["scope_key"] == "comments_per_hour"
    assert parsed["window_number"] == 12345


def test_parse_limit_key_invalid():
    """Invalid keys return None."""
    assert _parse_limit_key("invalid:key") is None
    assert _parse_limit_key("neuro:ws:wrong:a:b:c:1") is None
    assert _parse_limit_key("neuro:ws:limit:account:acc:comments_per_hour:not-int") is None
    assert _parse_limit_key("") is None


@freeze_time(_FROZEN_NOW)
def test_flush_skips_malformed_matching_keys(db_session):
    """Malformed matching Redis keys are ignored instead of aborting the flush."""
    redis = FakeRedis()
    redis.set("neuro:ws:limit:account:acc:comments_per_hour:not-int", "5")

    report = flush_redis_to_db(db_session, redis, now=_FROZEN_DT)

    assert report.total_keys_scanned == 0
    assert report.upserted == 0


@freeze_time(_FROZEN_NOW)
def test_flush_daily_scope(db_session):
    """Flush also handles daily scope keys."""
    redis = FakeRedis()
    window_seconds = 86400
    window_number = int(_FROZEN_DT.timestamp() // window_seconds)
    key = _make_redis_key(
        _WORKSPACE_ID, "campaign", _CAMPAIGN_ID, "comments_per_day", window_number
    )
    redis.set(key, "42")

    report = flush_redis_to_db(db_session, redis, now=_FROZEN_DT)
    db_session.commit()

    assert report.upserted == 1
    assert report.per_scope_counts.get("comments_per_day") == 1

    row = (
        db_session.query(RateLimitPersistentCounter)
        .filter_by(
            scope_key="comments_per_day",
        )
        .first()
    )
    assert row is not None
    assert row.count == 42


@freeze_time(_FROZEN_NOW)
def test_flush_bulk_upserts_1000_keys_under_100ms(db_session):
    """Flush 1000 Redis counters in one bulk upsert transaction."""
    redis = FakeRedis()
    window_seconds = 3600
    window_number = int(_FROZEN_DT.timestamp() // window_seconds)
    for i in range(1000):
        key = _make_redis_key(
            _WORKSPACE_ID,
            "account",
            f"acc-bulk-{i:028d}",
            "comments_per_hour",
            window_number,
        )
        redis.set(key, str((i % 5) + 1))

    started_at = perf_counter()
    report = flush_redis_to_db(db_session, redis, now=_FROZEN_DT)
    db_session.commit()
    elapsed_ms = (perf_counter() - started_at) * 1000

    assert report.upserted == 1000
    assert elapsed_ms <= 100
