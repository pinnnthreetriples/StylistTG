"""Atomic safety gate reserve via Redis Lua script.

Closes the TOCTOU race window between evaluate() and send:
- Atomically checks concurrency counter AND reserves a slot
- Auto-expires on TTL (crash safety)
- Sender calls reserve() → send → release()

Task 22: Concurrency-safe gate through Lua.
Task 44 (F-301, F-305, B F-004):
- Default fail-closed on Redis outage; opt-in fail-open via
  ``settings.safety_gate_redis_fail_open`` with explicit metric.
- Replace INCR-based counter with a ZSET keyed by reservation timestamp so
  expired reservations are cleaned up on every reserve call. This removes
  the B F-004 counter inflation that happened when reservation keys
  TTL-expired without their parallel counter being decremented.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError

from app.config import settings
from app.observability.safety_metrics import safety_metrics

GATE_RESERVE_TTL_SECONDS = 120
GATE_MAX_CONCURRENT_DEFAULT = 3

# ZSET-based reserve script.
# - KEYS[1]   : zset key  ``safety:gate:reservations:{account}:{intent}``
# - ARGV[1]   : now (unix seconds)
# - ARGV[2]   : ttl_seconds
# - ARGV[3]   : max_concurrent
# - ARGV[4]   : reservation_id
# - Returns {1, current_count} on success, {0, current_count} on limit reached.
#
# On each call the script first removes reservations whose timestamp is older
# than ``now - ttl_seconds`` — this is what gives us TTL parity with the old
# detail keys without needing a separate counter that could drift.
_RESERVE_LUA = """
local zset_key = KEYS[1]
local now = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local max_concurrent = tonumber(ARGV[3])
local reservation_id = ARGV[4]

redis.call('ZREMRANGEBYSCORE', zset_key, '-inf', now - ttl)
local current = tonumber(redis.call('ZCARD', zset_key))
if current >= max_concurrent then
  return {0, current}
end
redis.call('ZADD', zset_key, now, reservation_id)
redis.call('EXPIRE', zset_key, ttl * 2)
return {1, current + 1}
"""

_RELEASE_LUA = """
local zset_key = KEYS[1]
local reservation_id = ARGV[1]
local removed = redis.call('ZREM', zset_key, reservation_id)
return removed
"""


@dataclass(frozen=True)
class SafetyGateReservation:
    reservation_id: str
    account_id: str
    intent: str
    reserved: bool
    current_count: int
    max_concurrent: int
    degraded: bool = False
    """Set to ``True`` when the reservation was granted under the opt-in
    fail-open path because Redis was unreachable. Sender code can branch on
    this flag if it wants to add extra logging or refuse to proceed for very
    high-risk intents."""


def _zset_key(account_id: str, intent: str) -> str:
    # Versioned prefix so deploys that change the script don't double-count.
    return f"safety:gate:reservations:v2:{account_id}:{intent}"


def reserve(
    redis_client: Any,
    *,
    account_id: str,
    intent: str,
    max_concurrent: int = GATE_MAX_CONCURRENT_DEFAULT,
    ttl_seconds: int = GATE_RESERVE_TTL_SECONDS,
) -> SafetyGateReservation:
    """Atomically reserve a concurrency slot for account+intent.

    Returns SafetyGateReservation with reserved=True on success,
    reserved=False if concurrency limit is reached.

    On Redis failure: default ``fail-closed`` (``reserved=False``,
    ``degraded=True``) so a Redis outage cannot bypass concurrency control
    and produce duplicate sends. The operator can override per
    ``settings.safety_gate_redis_fail_open=True`` — that path also emits
    ``safety_gate_redis_fail_open_total`` so the override is visible.
    """
    reservation_id = uuid4().hex
    zset_key = _zset_key(account_id, intent)
    now = time.time()

    try:
        result = redis_client.eval(
            _RESERVE_LUA,
            1,
            zset_key,
            str(now),
            str(ttl_seconds),
            str(max_concurrent),
            reservation_id,
        )
    except RedisError:
        if settings.safety_gate_redis_fail_open:
            safety_metrics.redis_fail_open(operation="reserve")
            safety_metrics.reserve_outcome(outcome="RESERVED")
            return SafetyGateReservation(
                reservation_id=reservation_id,
                account_id=account_id,
                intent=intent,
                reserved=True,
                current_count=0,
                max_concurrent=max_concurrent,
                degraded=True,
            )
        safety_metrics.redis_outage(operation="reserve")
        safety_metrics.reserve_outcome(outcome="REDIS_UNAVAILABLE")
        return SafetyGateReservation(
            reservation_id=reservation_id,
            account_id=account_id,
            intent=intent,
            reserved=False,
            current_count=0,
            max_concurrent=max_concurrent,
            degraded=True,
        )

    reserved = int(result[0]) == 1
    current_count = int(result[1])
    safety_metrics.reserve_outcome(outcome="RESERVED" if reserved else "RATE_BLOCKED")
    return SafetyGateReservation(
        reservation_id=reservation_id,
        account_id=account_id,
        intent=intent,
        reserved=reserved,
        current_count=current_count,
        max_concurrent=max_concurrent,
    )


def release(
    redis_client: Any,
    *,
    reservation: SafetyGateReservation,
) -> bool:
    """Release a previously acquired reservation slot.

    Returns True if successfully released, False if reservation was already
    expired, not found, or the reservation was granted under fail-open
    degraded mode (where Redis is presumed unreachable).
    """
    if not reservation.reserved or reservation.degraded:
        return False

    zset_key = _zset_key(reservation.account_id, reservation.intent)

    try:
        result = redis_client.eval(
            _RELEASE_LUA,
            1,
            zset_key,
            reservation.reservation_id,
        )
        return int(result) == 1
    except RedisError:
        safety_metrics.redis_outage(operation="release")
        return False


def get_redis_client() -> Any:
    """Get Redis client from settings for gate reserve operations."""
    return cast(Any, Redis).from_url(settings.redis_url)


__all__ = [
    "GATE_MAX_CONCURRENT_DEFAULT",
    "GATE_RESERVE_TTL_SECONDS",
    "SafetyGateReservation",
    "get_redis_client",
    "release",
    "reserve",
]
