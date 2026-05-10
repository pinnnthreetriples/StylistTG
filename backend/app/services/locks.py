from __future__ import annotations

from datetime import timedelta
from contextlib import contextmanager
from dataclasses import dataclass
import uuid
from typing import Any, cast

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import or_, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AccountRuntimeState, utc_now


@dataclass(frozen=True)
class RedisLockHandle:
    key: str
    owner: str
    acquired: bool


def account_lock_key(*, workspace_id: str, account_id: str, purpose: str) -> str:
    if purpose not in {"execution", "lifecycle"}:
        raise ValueError("unsupported lock purpose")
    return f"locks:account:{workspace_id}:{account_id}:{purpose}"


def acquire_redis_account_lock(
    redis: Redis,
    *,
    workspace_id: str,
    account_id: str,
    purpose: str,
    ttl_seconds: int,
    owner: str | None = None,
) -> RedisLockHandle:
    key = account_lock_key(workspace_id=workspace_id, account_id=account_id, purpose=purpose)
    token = owner or f"lock:{uuid.uuid4()}"
    try:
        acquired = bool(redis.set(key, token, nx=True, ex=max(1, ttl_seconds)))
    except RedisError:
        acquired = False
    return RedisLockHandle(key=key, owner=token, acquired=acquired)


def release_redis_account_lock(redis: Redis, handle: RedisLockHandle) -> bool:
    try:
        if not _redis_value_matches(redis.get(handle.key), handle.owner):
            return False
        return bool(redis.delete(handle.key))
    except RedisError:
        return False


def refresh_redis_account_lock(redis: Redis, handle: RedisLockHandle, *, ttl_seconds: int) -> bool:
    try:
        if not _redis_value_matches(redis.get(handle.key), handle.owner):
            return False
        return bool(redis.expire(handle.key, max(1, ttl_seconds)))
    except RedisError:
        return False


@contextmanager
def account_redis_lock(
    redis: Redis,
    *,
    workspace_id: str,
    account_id: str,
    purpose: str,
    ttl_seconds: int,
    owner: str | None = None,
):
    handle = acquire_redis_account_lock(
        redis,
        workspace_id=workspace_id,
        account_id=account_id,
        purpose=purpose,
        ttl_seconds=ttl_seconds,
        owner=owner,
    )
    try:
        yield handle
    finally:
        if handle.acquired:
            release_redis_account_lock(redis, handle)


def acquire_account_lock(session: Session, account_id: str, owner: str) -> int | None:
    now = utc_now()
    stale_cutoff = now - timedelta(seconds=settings.lock_stale_seconds)
    result = cast(CursorResult[Any], session.execute(
        update(AccountRuntimeState)
        .where(AccountRuntimeState.account_id == account_id)
        .where(
            or_(
                AccountRuntimeState.lock_owner.is_(None),
                AccountRuntimeState.updated_at.is_(None),
                AccountRuntimeState.updated_at < stale_cutoff,
            )
        )
        .values(
            lock_owner=owner,
            lock_epoch=AccountRuntimeState.lock_epoch + 1,
            recovery_marker=f"lock_acquired:{owner}",
            updated_at=now,
        )
    ))
    if result.rowcount != 1:
        session.rollback()
        return None
    session.commit()
    runtime = session.get(AccountRuntimeState, account_id)
    if runtime is None or runtime.lock_owner != owner:
        return None
    return runtime.lock_epoch


def heartbeat_lock(session: Session, account_id: str, owner: str, lock_epoch: int) -> bool:
    runtime = session.get(AccountRuntimeState, account_id)
    if runtime is None or runtime.lock_owner != owner or runtime.lock_epoch != lock_epoch:
        return False
    runtime.updated_at = utc_now()
    if not _is_hard_stop_marker(runtime.recovery_marker):
        runtime.recovery_marker = f"heartbeat:{owner}"
    session.commit()
    return True


def release_account_lock(session: Session, account_id: str, owner: str, lock_epoch: int) -> bool:
    runtime = session.get(AccountRuntimeState, account_id)
    if runtime is None or runtime.lock_owner != owner or runtime.lock_epoch != lock_epoch:
        return False
    runtime.lock_owner = None
    if not _is_hard_stop_marker(runtime.recovery_marker):
        runtime.recovery_marker = f"lock_released:{owner}"
    runtime.updated_at = utc_now()
    session.commit()
    return True


def fenced_write_allowed(
    session: Session, account_id: str, owner: str, lock_epoch: int
) -> bool:
    runtime = session.get(AccountRuntimeState, account_id)
    return bool(runtime and runtime.lock_owner == owner and runtime.lock_epoch == lock_epoch)


def _is_hard_stop_marker(marker: str | None) -> bool:
    return bool(marker and marker.startswith("tdlib_hard_stop:"))


def _redis_value_matches(value: object, expected: str) -> bool:
    if isinstance(value, bytes):
        return value.decode("utf-8") == expected
    return value == expected
