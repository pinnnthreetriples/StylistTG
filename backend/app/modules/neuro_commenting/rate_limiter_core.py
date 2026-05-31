from __future__ import annotations

from contextlib import suppress
import json
import time
from typing import Any
from uuid import uuid4

from redis.exceptions import RedisError

from app.config import settings
from app.models import NeuroCommentCampaign, NeuroCommentCampaignAccount, NeuroCommentTarget
from app.services.redis_client import redis_from_url

from app.modules.neuro_commenting.rate_limiter_shared import (
    _RESERVE_SCRIPT,
    RateLimitReservation,
    RateLimitScope,
    build_rate_limit_counter_key,
    build_rate_limit_counter_metadata_key,
    parse_rate_limit_counter_key,
)

class RateLimiterCoreMixin:
    def _resolve_scope(
        self,
        scope: RateLimitScope | None,
        *,
        campaign: NeuroCommentCampaign | None,
        account: NeuroCommentCampaignAccount | None,
        target: NeuroCommentTarget | None,
    ) -> RateLimitScope:
        if scope is not None:
            return scope
        if campaign is None:
            raise ValueError("campaign is required")
        return RateLimitScope(
            workspace_id=campaign.workspace_id,
            campaign_id=campaign.id,
            account_id=account.account_id if account is not None else None,
            target_id=target.id if target is not None else None,
            campaign_account_id=account.id if account is not None else None,
        )

    def _reserve_with_redis(self, scope: RateLimitScope) -> RateLimitReservation:
        redis = self._client()
        cooldown = self._active_cooldown(redis, scope)
        if cooldown is not None:
            return cooldown
        limits = self._matching_limits(scope)
        reservation_id = uuid4().hex
        counter_limits, parallel_limits = _split_counter_limits(limits)
        window_counter_keys = [self._limit_key(scope, limit) for limit in counter_limits]
        parallel_counter_keys = [self._parallel_key(scope, limit) for limit in parallel_limits]
        reserve_limits = self._reserve_limits(counter_limits, parallel_limits)
        reserve_keys = [*window_counter_keys, *parallel_counter_keys]
        last_comment_keys = self._last_comment_keys(scope, limits)
        result = self._eval_reservation(
            redis,
            scope=scope,
            reservation_id=reservation_id,
            reserve_keys=reserve_keys,
            parallel_counter_keys=parallel_counter_keys,
            reserve_limits=reserve_limits,
            last_comment_keys=last_comment_keys,
        )
        if int(result[0]) != 1:
            return self._denied_reservation(result)
        self._write_counter_metadata(redis, counter_limits, window_counter_keys)
        return RateLimitReservation(
            reservation_id=reservation_id,
            allowed=True,
            checked_limits=[self._limit_name(limit) for limit in limits],
        )

    def _reserve_limits(
        self, counter_limits: list[dict[str, Any]], parallel_limits: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return [
            *counter_limits,
            *[
                {
                    **limit,
                    "window_seconds": min(
                        int(limit.get("window_seconds") or self._reservation_ttl_seconds),
                        self._reservation_ttl_seconds,
                    ),
                }
                for limit in parallel_limits
            ],
        ]

    def _last_comment_keys(
        self, scope: RateLimitScope, limits: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return [
            {
                "key": (
                    f"neuro:{scope.workspace_id}:last_comment:"
                    f"{limit['scope_type']}:{limit['scope_id']}"
                ),
                "ttl": int(limit["window_seconds"]),
                "reserve_ttl": min(int(limit["window_seconds"]), self._reservation_ttl_seconds),
                "name": self._limit_name(limit),
            }
            for limit in limits
            if limit["limit_type"] == "min_delay_between_comments"
        ]

    def _eval_reservation(
        self,
        redis: Any,
        *,
        scope: RateLimitScope,
        reservation_id: str,
        reserve_keys: list[str],
        parallel_counter_keys: list[str],
        reserve_limits: list[dict[str, Any]],
        last_comment_keys: list[dict[str, Any]],
    ) -> Any:
        min_delay_keys = [item["key"] for item in last_comment_keys]
        payload = json.dumps(
            {
                "status": "active",
                "counter_keys": reserve_keys,
                "commit_release_keys": parallel_counter_keys,
                "rollback_counter_keys": reserve_keys,
                "last_comment_keys": last_comment_keys,
            }
        )
        return redis.eval(
            _RESERVE_SCRIPT,
            len(reserve_keys) + len(min_delay_keys),
            *reserve_keys,
            *min_delay_keys,
            self._reservation_key(scope.workspace_id, reservation_id),
            payload,
            self._reservation_ttl_seconds,
            len(reserve_limits),
            *self._lua_limit_args(reserve_limits),
            len(last_comment_keys),
            *self._lua_min_delay_args(last_comment_keys),
        )

    def _denied_reservation(self, result: Any) -> RateLimitReservation:
        denied_name = self._decode_lua_value(result[1])
        return RateLimitReservation(
            None,
            False,
            reason=self._denied_reason(denied_name),
            retry_after_seconds=max(1, int(result[2] or 1)),
        )

    def _client(self) -> Any:
        if self._redis is None:
            self._redis = redis_from_url()
        return self._redis

    def _matching_limits(self, scope: RateLimitScope) -> list[dict[str, Any]]:
        limits = self._limits or self._default_limits(scope)
        matched: list[dict[str, Any]] = []
        for limit in limits:
            scope_type = str(limit["scope_type"])
            actual_scope_id = self._scope_id(scope, scope_type)
            configured_scope_id = limit.get("scope_id")
            if actual_scope_id is None:
                continue
            if configured_scope_id is not None and actual_scope_id != configured_scope_id:
                continue
            normalized = dict(limit)
            normalized["scope_id"] = actual_scope_id
            matched.append(normalized)
        return matched

    def _default_limits(self, scope: RateLimitScope) -> list[dict[str, Any]]:
        defaults: list[dict[str, Any]] = [
            {
                "scope_type": "campaign",
                "scope_id": scope.campaign_id,
                "limit_type": "comments_per_hour",
                "max_value": settings.neuro_comment_default_campaign_comments_per_hour,
                "window_seconds": 3600,
            },
            {
                "scope_type": "campaign",
                "scope_id": scope.campaign_id,
                "limit_type": "comments_per_day",
                "max_value": settings.neuro_comment_default_campaign_comments_per_day,
                "window_seconds": 86400,
            },
            {
                "scope_type": "campaign",
                "scope_id": scope.campaign_id,
                "limit_type": "min_delay_between_comments",
                "max_value": settings.neuro_comment_default_min_delay_between_comments_seconds,
                "window_seconds": settings.neuro_comment_default_min_delay_between_comments_seconds,
            },
        ]
        if scope.account_id is not None:
            defaults.extend(
                [
                    {
                        "scope_type": "account",
                        "scope_id": scope.account_id,
                        "limit_type": "comments_per_hour",
                        "max_value": settings.neuro_comment_default_account_comments_per_hour,
                        "window_seconds": 3600,
                    },
                    {
                        "scope_type": "account",
                        "scope_id": scope.account_id,
                        "limit_type": "comments_per_day",
                        "max_value": settings.neuro_comment_default_account_comments_per_day,
                        "window_seconds": 86400,
                    },
                ]
            )
        if scope.target_id is not None:
            defaults.append(
                {
                    "scope_type": "target",
                    "scope_id": scope.target_id,
                    "limit_type": "comments_per_hour",
                    "max_value": settings.neuro_comment_default_target_comments_per_hour,
                    "window_seconds": 3600,
                }
            )
        return defaults

    def _lua_limit_args(self, limits: list[dict[str, Any]]) -> list[Any]:
        args: list[Any] = []
        for limit in limits:
            args.extend(
                [
                    self._limit_name(limit),
                    int(limit["max_value"]),
                    int(limit["window_seconds"]),
                ]
            )
        return args

    def _lua_min_delay_args(self, last_comment_keys: list[dict[str, Any]]) -> list[Any]:
        args: list[Any] = []
        for item in last_comment_keys:
            args.extend([item["name"], int(item["reserve_ttl"])])
        return args

    def _denied_reason(self, limit_name: str) -> str:
        if limit_name == "reservation_conflict":
            return "reservation_conflict"
        if " " not in limit_name:
            return limit_name
        scope, limit_type = limit_name.split(" ", 1)
        scope_type = scope.split(":", 1)[0]
        if limit_type == "min_delay_between_comments":
            return f"{scope_type} {limit_type} active"
        return f"{scope_type} {limit_type} limit exceeded"

    def _decode_lua_value(self, value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode()
        return str(value)

    def _active_cooldown(self, redis: Any, scope: RateLimitScope) -> RateLimitReservation | None:
        for scope_type in ("account", "target", "campaign"):
            scope_id = self._scope_id(scope, scope_type)
            if scope_id is None:
                continue
            key = f"neuro:{scope.workspace_id}:cooldown:{scope_type}:{scope_id}"
            if redis.get(key) is not None:
                return RateLimitReservation(
                    None,
                    False,
                    reason=f"{scope_type} cooldown active",
                    retry_after_seconds=max(1, int(redis.ttl(key))),
                )
        return None

    def _scope_id(self, scope: RateLimitScope, scope_type: str) -> str | None:
        return {
            "workspace": scope.workspace_id,
            "campaign": scope.campaign_id,
            "account": scope.account_id,
            "target": scope.target_id,
            "campaign_account": scope.campaign_account_id,
            "campaign_target": scope.campaign_target_id,
        }[scope_type]

    def _limit_key(self, scope: RateLimitScope, limit: dict[str, Any]) -> str:
        window = int(time.time() // int(limit["window_seconds"]))
        return build_rate_limit_counter_key(
            workspace_id=scope.workspace_id,
            scope_type=str(limit["scope_type"]),
            scope_id=str(limit["scope_id"]),
            scope_key=str(limit["limit_type"]),
            window_number=window,
        )

    def _write_counter_metadata(
        self, redis: Any, limits: list[dict[str, Any]], counter_keys: list[str]
    ) -> None:
        with suppress(RedisError, AttributeError):
            pipeline = redis.pipeline()
            for limit, counter_key in zip(limits, counter_keys, strict=True):
                parsed = parse_rate_limit_counter_key(counter_key)
                if parsed is None:
                    continue
                window_seconds = int(limit["window_seconds"])
                metadata_key = build_rate_limit_counter_metadata_key(
                    workspace_id=parsed.workspace_id,
                    scope_type=parsed.scope_type,
                    scope_id=parsed.scope_id,
                    scope_key=parsed.scope_key,
                    window_number=parsed.window_number,
                )
                pipeline.set(metadata_key, str(window_seconds), ex=max(1, window_seconds * 2))
            pipeline.execute()

    def _parallel_key(self, scope: RateLimitScope, limit: dict[str, Any]) -> str:
        return f"neuro:{scope.workspace_id}:parallel:{limit['scope_type']}:{limit['scope_id']}"

    def _reservation_key(self, workspace_id: str, reservation_id: str) -> str:
        return f"neuro:{workspace_id}:reservation:{reservation_id}"

    def _limit_name(self, limit: dict[str, Any]) -> str:
        return f"{limit['scope_type']}:{limit['scope_id']} {limit['limit_type']}"

    def _find_reservation_keys(self, redis: Any, reservation_id: str) -> list[str]:
        if hasattr(redis, "keys"):
            return [
                key.decode() if isinstance(key, bytes) else key
                for key in redis.keys(f"neuro:*:reservation:{reservation_id}")
            ]
        values = getattr(redis, "values", {})
        return [key for key in values if str(key).endswith(f":reservation:{reservation_id}")]

    def _loads(self, raw: Any) -> dict[str, Any]:
        if raw is None:
            return {}
        if isinstance(raw, bytes):
            raw = raw.decode()
        return json.loads(str(raw))


def _split_counter_limits(
    limits: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    counter_limits = [
        item
        for item in limits
        if item["limit_type"] not in {"min_delay_between_comments", "max_parallel_attempts"}
    ]
    parallel_limits = [item for item in limits if item["limit_type"] == "max_parallel_attempts"]
    return counter_limits, parallel_limits
