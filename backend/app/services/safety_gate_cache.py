from __future__ import annotations

from typing import Protocol, cast

from redis import Redis
from redis.exceptions import RedisError

from app.services.redis_client import redis_from_url


class SafetyGateCache(Protocol):
    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str, *, ttl_seconds: int) -> None: ...


class NullSafetyGateCache:
    def get(self, key: str) -> str | None:
        return None

    def set(self, key: str, value: str, *, ttl_seconds: int) -> None:
        return None


class InMemorySafetyGateCache:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    @property
    def size(self) -> int:
        return len(self._values)

    def get(self, key: str) -> str | None:
        return self._values.get(key)

    def set(self, key: str, value: str, *, ttl_seconds: int) -> None:
        self._values[key] = value


class RedisSafetyGateCache:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @classmethod
    def from_settings(cls) -> RedisSafetyGateCache:
        return cls(redis_from_url())

    def get(self, key: str) -> str | None:
        try:
            value = self._redis.get(key)
        except RedisError:
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return cast(str | None, value)

    def set(self, key: str, value: str, *, ttl_seconds: int) -> None:
        try:
            self._redis.set(key, value, ex=max(1, ttl_seconds))
        except RedisError:
            return


__all__ = [
    "InMemorySafetyGateCache",
    "NullSafetyGateCache",
    "RedisSafetyGateCache",
    "SafetyGateCache",
]
