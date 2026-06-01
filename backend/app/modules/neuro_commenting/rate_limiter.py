from __future__ import annotations

# pyright: reportUnusedImport=false

import json
from typing import Any

from redis.exceptions import RedisError

from app.config import settings
from app.models import NeuroCommentCampaign, NeuroCommentCampaignAccount, NeuroCommentTarget
from app.modules.neuro_commenting.rate_limiter_core import RateLimiterCoreMixin
from app.services.redis_client import redis_from_url

from app.modules.neuro_commenting.rate_limiter_shared import (  # noqa: F401
    RATE_LIMIT_COUNTER_SCAN_PATTERN,
    RateLimitReservation,
    RateLimitScope,
    build_rate_limit_counter_key,
    build_rate_limit_counter_metadata_key,
    parse_rate_limit_counter_key,
)


class NeuroCommentRateLimiter(RateLimiterCoreMixin):
    def __init__(
        self,
        *,
        redis_client: Any | None = None,
        limits: list[dict[str, Any]] | None = None,
        enabled: bool | None = None,
        fail_closed: bool | None = None,
        reservation_ttl_seconds: int | None = None,
    ) -> None:
        self._redis = redis_client
        self._limits = limits
        self._enabled = settings.neuro_comment_rate_limiter_enabled if enabled is None else enabled
        self._fail_closed = (
            settings.neuro_comment_rate_limiter_fail_closed if fail_closed is None else fail_closed
        )
        self._reservation_ttl_seconds = (
            settings.neuro_comment_rate_limiter_reservation_ttl_seconds
            if reservation_ttl_seconds is None
            else reservation_ttl_seconds
        )

    def _client(self) -> Any:
        if self._redis is None:
            self._redis = redis_from_url()
        return self._redis

    def reserve(
        self,
        scope: RateLimitScope | None = None,
        *,
        campaign: NeuroCommentCampaign | None = None,
        account: NeuroCommentCampaignAccount | None = None,
        target: NeuroCommentTarget | None = None,
    ) -> RateLimitReservation:
        if not self._enabled:
            return RateLimitReservation(None, True)
        scope = self._resolve_scope(scope, campaign=campaign, account=account, target=target)
        try:
            return self._reserve_with_redis(scope)
        except RedisError:
            if self._fail_closed:
                return RateLimitReservation(
                    None, False, reason="rate_limiter_unavailable", retry_after_seconds=60
                )
            return RateLimitReservation(None, True, reason="rate_limiter_unavailable")

    def commit(self, reservation: RateLimitReservation) -> None:
        if not reservation.allowed or reservation.reservation_id is None:
            return
        try:
            redis = self._client()
            for key in self._find_reservation_keys(redis, reservation.reservation_id):
                raw = redis.get(key)
                data = self._loads(raw)
                if data.get("status") != "active":
                    return
                data["status"] = "committed"
                redis.set(key, json.dumps(data), ex=self._reservation_ttl_seconds)
                release_keys = data.get("commit_release_keys", [])
                if release_keys:
                    pipeline = redis.pipeline()
                    for counter_key in release_keys:
                        pipeline.decrby(counter_key, 1)
                    pipeline.execute()
                for item in data.get("last_comment_keys", []):
                    redis.set(item["key"], "1", ex=max(1, int(item["ttl"])))
                redis.delete(key)
        except RedisError:
            return

    def rollback(self, reservation: RateLimitReservation) -> None:
        if not reservation.allowed or reservation.reservation_id is None:
            return
        try:
            redis = self._client()
            for key in self._find_reservation_keys(redis, reservation.reservation_id):
                raw = redis.get(key)
                data = self._loads(raw)
                if data.get("status") != "active":
                    return
                pipeline = redis.pipeline()
                for counter_key in data.get("rollback_counter_keys", data.get("counter_keys", [])):
                    pipeline.decrby(counter_key, 1)
                for item in data.get("last_comment_keys", []):
                    pipeline.delete(item["key"])
                pipeline.delete(key)
                pipeline.execute()
        except RedisError:
            return

    def cooldown(
        self,
        *,
        workspace_id: str,
        scope_type: str,
        scope_id: str,
        seconds: int,
        reason: str,
    ) -> None:
        redis = self._client()
        redis.set(
            f"neuro:{workspace_id}:cooldown:{scope_type}:{scope_id}",
            reason,
            ex=max(1, seconds),
        )
