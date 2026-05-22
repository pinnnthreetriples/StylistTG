"""Atomic safety gate reserve via Redis Lua script.

Closes the TOCTOU race window between evaluate() and send:
- Atomically checks concurrency counter AND reserves a slot
- Auto-expires on TTL (crash safety)
- Sender calls reserve() → send → release()

Task 22: Concurrency-safe gate through Lua.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError

from app.config import settings
from app.observability.safety_metrics import safety_metrics

GATE_RESERVE_TTL_SECONDS = 120
GATE_MAX_CONCURRENT_DEFAULT = 3

_RESERVE_LUA = """
-- safety_gate_reserve_v1
-- KEYS[1] = concurrency counter key
-- KEYS[2] = reservation detail key
-- ARGV[1] = max_concurrent
-- ARGV[2] = reservation_id
-- ARGV[3] = ttl_seconds
-- Returns: {1, current_count} on success, {0, current_count} on limit reached

local counter_key = KEYS[1]
local reservation_key = KEYS[2]
local max_concurrent = tonumber(ARGV[1])
local reservation_id = ARGV[2]
local ttl = tonumber(ARGV[3])

local current = tonumber(redis.call("GET", counter_key) or "0")
if current >= max_concurrent then
  return {0, current}
end

redis.call("INCRBY", counter_key, 1)
if redis.call("TTL", counter_key) < 0 then
  redis.call("EXPIRE", counter_key, ttl * 2)
end
redis.call("SET", reservation_key, "active", "EX", ttl)
return {1, current + 1}
"""

_RELEASE_LUA = """
-- safety_gate_release_v1
-- KEYS[1] = concurrency counter key
-- KEYS[2] = reservation detail key
-- Returns: 1 on success, 0 if reservation not found

local counter_key = KEYS[1]
local reservation_key = KEYS[2]

local exists = redis.call("GET", reservation_key)
if not exists then
  return 0
end
redis.call("DEL", reservation_key)
local current = tonumber(redis.call("GET", counter_key) or "0")
if current > 0 then
  redis.call("DECRBY", counter_key, 1)
end
return 1
"""


@dataclass(frozen=True)
class SafetyGateReservation:
    reservation_id: str
    account_id: str
    intent: str
    reserved: bool
    current_count: int
    max_concurrent: int


def _counter_key(account_id: str, intent: str) -> str:
    return f"safety:gate:concurrent:{account_id}:{intent}"


def _reservation_key(account_id: str, reservation_id: str) -> str:
    return f"safety:gate:reservation:{account_id}:{reservation_id}"


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
    """
    reservation_id = uuid4().hex
    counter_key = _counter_key(account_id, intent)
    reservation_key = _reservation_key(account_id, reservation_id)

    try:
        result = redis_client.eval(
            _RESERVE_LUA,
            2,
            counter_key,
            reservation_key,
            max_concurrent,
            reservation_id,
            ttl_seconds,
        )
        reserved = int(result[0]) == 1
        current_count = int(result[1])
    except RedisError:
        # Fail-open: if Redis is down, allow the operation
        safety_metrics.reserve_outcome(outcome="RESERVED")
        return SafetyGateReservation(
            reservation_id=reservation_id,
            account_id=account_id,
            intent=intent,
            reserved=True,
            current_count=0,
            max_concurrent=max_concurrent,
        )

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
    expired or not found.
    """
    if not reservation.reserved:
        return False

    counter_key = _counter_key(reservation.account_id, reservation.intent)
    reservation_key = _reservation_key(reservation.account_id, reservation.reservation_id)

    try:
        result = redis_client.eval(
            _RELEASE_LUA,
            2,
            counter_key,
            reservation_key,
        )
        return int(result) == 1
    except RedisError:
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
