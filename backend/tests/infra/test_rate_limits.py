from __future__ import annotations

from redis.exceptions import RedisError

from app.services.rate_limits import evaluate_tenant_rate_limit


class FakeRedis:
    def __init__(self, *, start_count: int = 0) -> None:
        self.calls: list[tuple] = []
        self.value = start_count

    def pipeline(self):
        return self

    def incr(self, key: str):
        self.calls.append(("incr", key))
        return self

    def expire(self, key: str, ttl: int, nx: bool = False):
        self.calls.append(("expire", key, ttl, nx))
        return self

    def ttl(self, key: str):
        self.calls.append(("ttl", key))
        return self

    def execute(self):
        self.value += 1
        return [self.value, True, 3600]


def test_rate_limit_sets_ttl_in_same_pipeline_as_increment() -> None:
    redis = FakeRedis()

    decision = evaluate_tenant_rate_limit(
        redis,
        workspace_id="workspace-1",
        action_type="job.enqueue",
        queue_name="profile_jobs",
    )

    assert decision.allowed is True
    assert redis.calls == [
        ("incr", "rate:workspace-1:tenant:profile_jobs:job.enqueue"),
        ("expire", "rate:workspace-1:tenant:profile_jobs:job.enqueue", 3600, True),
        ("ttl", "rate:workspace-1:tenant:profile_jobs:job.enqueue"),
    ]


def test_rate_limit_returns_controlled_error_when_pipeline_fails() -> None:
    class FailingRedis(FakeRedis):
        def execute(self):
            raise RedisError("offline")

    decision = evaluate_tenant_rate_limit(
        FailingRedis(),
        workspace_id="workspace-1",
        action_type="job.enqueue",
    )

    assert decision.allowed is False
    assert decision.reason == "rate_limit_store_unavailable"


def _evaluate(redis: "FakeRedis", *, account_id: str | None = None):
    return evaluate_tenant_rate_limit(
        redis,
        workspace_id="workspace-1",
        action_type="job.enqueue",
        queue_name="profile_jobs",
        **({"account_id": account_id} if account_id is not None else {}),
    )


def test_tenant_rate_limit_exceeded_when_count_exceeds_limit() -> None:
    decision = _evaluate(FakeRedis(start_count=100))

    assert decision.allowed is False
    assert decision.reason == "tenant_rate_limit_exceeded"
    assert decision.remaining == 0
    assert decision.retry_after_seconds == 3600


def test_account_rate_limit_exceeded_when_count_exceeds_limit() -> None:
    decision = _evaluate(FakeRedis(start_count=100), account_id="account-1")

    assert decision.allowed is False
    assert decision.reason == "account_rate_limit_exceeded"
    assert decision.remaining == 0


def test_rate_limit_remaining_decrements_correctly() -> None:
    decision = _evaluate(FakeRedis(start_count=98))

    assert decision.allowed is True
    assert decision.remaining == 1
