from __future__ import annotations

from redis.exceptions import RedisError

from app.services.neuro_commenting.rate_limiter import (
    NeuroCommentRateLimiter,
    RateLimitScope,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int | str] = {}
        self.ttls: dict[str, int] = {}
        self.deleted: set[str] = set()

    def get(self, key: str):
        return self.values.get(key)

    def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True

    def delete(self, *keys: str):
        for key in keys:
            self.values.pop(key, None)
            self.deleted.add(key)
        return len(keys)

    def incrby(self, key: str, amount: int):
        self.values[key] = int(self.values.get(key, 0)) + amount
        return self.values[key]

    def decrby(self, key: str, amount: int):
        self.values[key] = int(self.values.get(key, 0)) - amount
        return self.values[key]

    def expire(self, key: str, ttl: int, nx: bool = False):
        if key not in self.values:
            return 0
        if nx and key in self.ttls:
            return 0
        self.ttls[key] = ttl
        return 1

    def ttl(self, key: str):
        return self.ttls.get(key, -1)

    def pipeline(self):
        return FakePipeline(self)

    def eval(self, script: str, numkeys: int, *args):
        keys = list(args[:numkeys])
        argv = list(args[numkeys:])
        if "reserve_limit_v1" in script:
            reservation_key = str(argv[0])
            reservation_payload = str(argv[1])
            reservation_ttl = int(argv[2])
            limit_count = int(argv[3])
            cursor = 4
            checked: list[tuple[str, str, int, int]] = []
            for index in range(limit_count):
                key = str(keys[index])
                name = str(argv[cursor])
                max_value = int(argv[cursor + 1])
                window_seconds = int(argv[cursor + 2])
                cursor += 3
                current = int(self.values.get(key, 0))
                if current >= max_value:
                    return [0, name, self.ttl(key)]
                checked.append((key, name, max_value, window_seconds))
            for key, _name, _max_value, window_seconds in checked:
                self.incrby(key, 1)
                self.expire(key, window_seconds, nx=True)
            self.set(reservation_key, reservation_payload, ex=reservation_ttl, nx=True)
            return [1, "", 0]
        raise AssertionError("unexpected lua script")


class FakePipeline:
    def __init__(self, redis: FakeRedis) -> None:
        self.redis = redis
        self.commands: list[tuple] = []

    def incrby(self, key: str, amount: int):
        self.commands.append(("incrby", key, amount))
        return self

    def decrby(self, key: str, amount: int):
        self.commands.append(("decrby", key, amount))
        return self

    def expire(self, key: str, ttl: int, nx: bool = False):
        self.commands.append(("expire", key, ttl, nx))
        return self

    def delete(self, *keys: str):
        self.commands.append(("delete", keys))
        return self

    def execute(self):
        results = []
        for command in self.commands:
            if command[0] == "incrby":
                results.append(self.redis.incrby(command[1], command[2]))
            elif command[0] == "decrby":
                results.append(self.redis.decrby(command[1], command[2]))
            elif command[0] == "expire":
                results.append(self.redis.expire(command[1], command[2], nx=command[3]))
            elif command[0] == "delete":
                results.append(self.redis.delete(*command[1]))
        return results


class FailingRedis(FakeRedis):
    def get(self, key: str):
        raise RedisError("redis down")


def _scope() -> RateLimitScope:
    return RateLimitScope(
        workspace_id="workspace-1",
        campaign_id="campaign-1",
        account_id="account-1",
        target_id="target-1",
    )


def test_reserve_allows_under_limit_and_commit_consumes_capacity() -> None:
    redis = FakeRedis()
    limiter = NeuroCommentRateLimiter(
        redis_client=redis,
        limits=[
            {
                "scope_type": "account",
                "scope_id": "account-1",
                "limit_type": "comments_per_hour",
                "max_value": 1,
                "window_seconds": 3600,
            }
        ],
    )

    reservation = limiter.reserve(_scope())
    limiter.commit(reservation)
    denied = limiter.reserve(_scope())

    assert reservation.allowed is True
    assert reservation.reservation_id is not None
    assert denied.allowed is False
    assert denied.reason == "account comments_per_hour limit exceeded"


def test_rollback_restores_capacity_and_is_idempotent() -> None:
    redis = FakeRedis()
    limiter = NeuroCommentRateLimiter(
        redis_client=redis,
        limits=[
            {
                "scope_type": "campaign",
                "scope_id": "campaign-1",
                "limit_type": "comments_per_day",
                "max_value": 1,
                "window_seconds": 86400,
            }
        ],
    )

    reservation = limiter.reserve(_scope())
    limiter.rollback(reservation)
    limiter.rollback(reservation)

    assert limiter.reserve(_scope()).allowed is True


def test_min_delay_and_cooldown_block_reserve() -> None:
    redis = FakeRedis()
    limiter = NeuroCommentRateLimiter(
        redis_client=redis,
        limits=[
            {
                "scope_type": "target",
                "scope_id": "target-1",
                "limit_type": "min_delay_between_comments",
                "max_value": 10,
                "window_seconds": 10,
            }
        ],
    )

    first = limiter.reserve(_scope())
    limiter.commit(first)
    second = limiter.reserve(_scope())
    limiter.cooldown(
        workspace_id="workspace-1",
        scope_type="account",
        scope_id="account-1",
        seconds=30,
        reason="FLOOD_WAIT",
    )
    cooled_down = limiter.reserve(_scope())

    assert second.allowed is False
    assert second.reason == "target min_delay_between_comments active"
    assert cooled_down.allowed is False
    assert cooled_down.reason == "account cooldown active"


def test_commit_sets_min_delay_ttl_from_limit() -> None:
    redis = FakeRedis()
    limiter = NeuroCommentRateLimiter(
        redis_client=redis,
        limits=[
            {
                "scope_type": "target",
                "scope_id": "target-1",
                "limit_type": "min_delay_between_comments",
                "max_value": 10,
                "window_seconds": 10,
            }
        ],
    )

    reservation = limiter.reserve(_scope())
    limiter.commit(reservation)

    assert redis.ttl("neuro:workspace-1:last_comment:target:target-1") == 10


def test_max_parallel_attempts_releases_capacity_on_commit() -> None:
    redis = FakeRedis()
    limiter = NeuroCommentRateLimiter(
        redis_client=redis,
        limits=[
            {
                "scope_type": "account",
                "scope_id": "account-1",
                "limit_type": "max_parallel_attempts",
                "max_value": 1,
                "window_seconds": 300,
            }
        ],
    )

    first = limiter.reserve(_scope())
    denied = limiter.reserve(_scope())
    limiter.commit(first)
    after_commit = limiter.reserve(_scope())

    assert first.allowed is True
    assert denied.allowed is False
    assert denied.reason == "account max_parallel_attempts limit exceeded"
    assert after_commit.allowed is True


def test_redis_unavailable_fails_closed() -> None:
    limiter = NeuroCommentRateLimiter(redis_client=FailingRedis(), fail_closed=True)

    reservation = limiter.reserve(_scope())

    assert reservation.allowed is False
    assert reservation.reason == "rate_limiter_unavailable"
