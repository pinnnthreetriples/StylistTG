"""Coverage for Task 44 / F-301, F-305, B F-004: Redis-degraded safety gate.

Three groups of behaviors exercised here:

* **F-301** — When Redis raises, ``reserve()`` returns a non-reserved
  ``SafetyGateReservation`` by default (fail-closed). The metric
  ``safety_gate_redis_errors_total{operation="reserve"}`` is incremented.
* **F-301 escape hatch** — ``settings.safety_gate_redis_fail_open=True``
  makes the same outage path grant the reservation with ``degraded=True``
  and emit ``safety_gate_redis_fail_open_total{operation="reserve"}``.
* **B F-004** — The ZSET-based Lua script removes timestamp-expired
  reservations on every reserve call, so a reservation key that drops out
  of TTL does not inflate the counter. Tests assert correct counts when
  reservations expire and when concurrent reserves hit the limit.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

try:
    import fakeredis
except ImportError:  # pragma: no cover - skipped if dev deps not installed.
    fakeredis = None  # type: ignore[assignment]

from app.services.safety_gate_reserve import (
    GATE_MAX_CONCURRENT_DEFAULT,
    SafetyGateReservation,
    release,
    reserve,
)

pytestmark = pytest.mark.skipif(fakeredis is None, reason="fakeredis not installed")


@pytest.fixture()
def fake_redis():
    return fakeredis.FakeRedis()


@pytest.fixture()
def broken_redis():
    class _Broken:
        def eval(self, *args, **kwargs):
            raise RedisConnectionError("simulated outage")

    return _Broken()


# ---------------------------------------------------------------------------
# F-301: fail-closed default + opt-in fail-open
# ---------------------------------------------------------------------------


def test_redis_outage_default_fail_closed(broken_redis) -> None:
    with patch("app.services.safety_gate_reserve.settings") as cfg:
        cfg.safety_gate_redis_fail_open = False
        result = reserve(broken_redis, account_id="a-1", intent="commenting")
    assert result.reserved is False
    assert result.degraded is True


def test_redis_outage_fail_open_when_opted_in(broken_redis) -> None:
    with patch("app.services.safety_gate_reserve.settings") as cfg:
        cfg.safety_gate_redis_fail_open = True
        result = reserve(broken_redis, account_id="a-1", intent="commenting")
    assert result.reserved is True
    assert result.degraded is True


def test_degraded_reservation_is_not_released(broken_redis) -> None:
    """release() refuses to no-op decrement when the reservation was granted
    under fail-open: there is nothing in Redis to release."""
    with patch("app.services.safety_gate_reserve.settings") as cfg:
        cfg.safety_gate_redis_fail_open = True
        reservation = reserve(broken_redis, account_id="a-1", intent="commenting")
    assert release(broken_redis, reservation=reservation) is False


# ---------------------------------------------------------------------------
# Lua ZSET reserve happy path
# ---------------------------------------------------------------------------


def test_reserve_succeeds_under_limit(fake_redis) -> None:
    result = reserve(
        fake_redis,
        account_id="a-2",
        intent="commenting",
        max_concurrent=2,
    )
    assert result.reserved is True
    assert result.current_count == 1
    assert result.degraded is False


def test_concurrent_reserves_respect_limit(fake_redis) -> None:
    r1 = reserve(fake_redis, account_id="a-3", intent="commenting", max_concurrent=1)
    r2 = reserve(fake_redis, account_id="a-3", intent="commenting", max_concurrent=1)
    assert r1.reserved is True
    assert r2.reserved is False
    assert r2.current_count == 1


def test_release_frees_the_slot(fake_redis) -> None:
    r1 = reserve(fake_redis, account_id="a-4", intent="commenting", max_concurrent=1)
    assert release(fake_redis, reservation=r1) is True
    r2 = reserve(fake_redis, account_id="a-4", intent="commenting", max_concurrent=1)
    assert r2.reserved is True


# ---------------------------------------------------------------------------
# B F-004: ZSET TTL parity — expired reservations are dropped.
# ---------------------------------------------------------------------------


def test_expired_reservation_does_not_inflate_counter(fake_redis) -> None:
    """Simulate a reservation that aged past the TTL window. Because the
    Lua script removes timestamp-expired entries on every reserve, the
    counter recovers to 0 and a fresh reservation succeeds."""
    # Place a stale entry with an ancient timestamp directly into the ZSET.
    zset_key = "safety:gate:reservations:v2:a-5:commenting"
    fake_redis.zadd(zset_key, {"stale-reservation": 0})  # epoch 0 → far past
    fake_redis.zadd(zset_key, {"another-stale": 10})

    # Now reserve with a short max_concurrent; both stale entries should
    # be pruned and the new reservation succeed.
    result = reserve(
        fake_redis,
        account_id="a-5",
        intent="commenting",
        max_concurrent=2,
        ttl_seconds=120,
    )
    assert result.reserved is True
    assert result.current_count == 1  # the two stale entries were removed
    assert fake_redis.zcard(zset_key) == 1


def test_reservation_id_unique_within_zset(fake_redis) -> None:
    r1 = reserve(fake_redis, account_id="a-6", intent="commenting", max_concurrent=5)
    r2 = reserve(fake_redis, account_id="a-6", intent="commenting", max_concurrent=5)
    assert r1.reservation_id != r2.reservation_id
    zset_key = "safety:gate:reservations:v2:a-6:commenting"
    assert fake_redis.zcard(zset_key) == 2


def test_different_intents_have_isolated_counters(fake_redis) -> None:
    r1 = reserve(fake_redis, account_id="a-7", intent="commenting", max_concurrent=1)
    r2 = reserve(fake_redis, account_id="a-7", intent="warmup", max_concurrent=1)
    assert r1.reserved is True
    assert r2.reserved is True


def test_dataclass_is_immutable() -> None:
    """SafetyGateReservation is frozen — callers can't sneak the reserved
    flag back to True after a fail-closed outcome."""
    r = SafetyGateReservation(
        reservation_id="x",
        account_id="a",
        intent="commenting",
        reserved=False,
        current_count=0,
        max_concurrent=GATE_MAX_CONCURRENT_DEFAULT,
        degraded=True,
    )
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        r.reserved = True  # type: ignore[misc]
