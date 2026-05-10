from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from redis import Redis
from redis.exceptions import RedisError

from app.config import Settings, settings


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    reason: str | None = None
    retry_after_seconds: int | None = None
    remaining: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "retry_after_seconds": self.retry_after_seconds,
            "remaining": self.remaining,
        }


def evaluate_tenant_rate_limit(
    redis: Redis,
    *,
    workspace_id: str,
    action_type: str,
    account_id: str | None = None,
    queue_name: str | None = None,
    config: Settings = settings,
) -> RateLimitDecision:
    limit = _limit_for(action_type, queue_name=queue_name, config=config)
    key = _key(workspace_id=workspace_id, action_type=action_type, account_id=account_id, queue_name=queue_name)
    try:
        pipeline = cast(Any, redis).pipeline()
        pipeline.incr(key)
        pipeline.expire(key, 3600, nx=True)
        pipeline.ttl(key)
        count_raw, _expire_set, ttl_raw = pipeline.execute()
        count = int(count_raw)
        ttl = int(ttl_raw)
    except RedisError:
        return RateLimitDecision(allowed=False, reason="rate_limit_store_unavailable", retry_after_seconds=60)
    if count > limit:
        return RateLimitDecision(
            allowed=False,
            reason="tenant_rate_limit_exceeded" if account_id is None else "account_rate_limit_exceeded",
            retry_after_seconds=max(ttl, 1),
            remaining=0,
        )
    return RateLimitDecision(allowed=True, remaining=max(limit - count, 0), retry_after_seconds=max(ttl, 1))


def _limit_for(action_type: str, *, queue_name: str | None, config: Settings) -> int:
    if queue_name == "auth_jobs" or action_type.startswith("account.auth"):
        return config.rate_limit_auth_jobs_per_tenant_per_hour
    if queue_name == "media_jobs":
        return config.rate_limit_media_jobs_per_tenant_per_hour
    if queue_name == "story_jobs" or action_type.startswith("story."):
        return config.rate_limit_story_jobs_per_tenant_per_hour
    if queue_name == "profile_jobs" or action_type.startswith("profile.") or action_type == "job.enqueue":
        return config.rate_limit_profile_jobs_per_tenant_per_hour
    if action_type.startswith("account."):
        return config.rate_limit_account_jobs_per_hour
    return config.rate_limit_profile_jobs_per_tenant_per_hour


def _key(*, workspace_id: str, action_type: str, account_id: str | None, queue_name: str | None) -> str:
    scope = f"account:{account_id}" if account_id else "tenant"
    queue = queue_name or "none"
    return f"rate:{workspace_id}:{scope}:{queue}:{action_type}"
