from __future__ import annotations

from typing import Any

from redis import ConnectionPool, Redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from app.config import Settings, settings
from app.observability.safety_metrics import safety_metrics


class InstrumentedRedisConnectionPool(ConnectionPool):
    def get_connection(self, *args: Any, **kwargs: Any):
        connection = super().get_connection(*args, **kwargs)
        _record_pool_saturation(self)
        return connection

    def release(self, connection):
        try:
            return super().release(connection)
        finally:
            _record_pool_saturation(self)


def redis_connection_kwargs(
    config: Settings = settings,
    *,
    socket_timeout: float | None = None,
    socket_connect_timeout: float | None = None,
) -> dict[str, Any]:
    return {
        "socket_timeout": (
            config.redis_socket_timeout_sec if socket_timeout is None else socket_timeout
        ),
        "socket_connect_timeout": (
            config.redis_socket_connect_timeout_sec
            if socket_connect_timeout is None
            else socket_connect_timeout
        ),
        "socket_keepalive": True,
        "health_check_interval": config.redis_health_check_interval_sec,
        "max_connections": config.redis_max_connections,
        "retry_on_timeout": True,
        "retry": Retry(ExponentialBackoff(), retries=config.redis_retry_retries),
    }


def redis_from_url(
    url: str | None = None,
    *,
    config: Settings = settings,
    socket_timeout: float | None = None,
    socket_connect_timeout: float | None = None,
) -> Redis:
    pool = InstrumentedRedisConnectionPool.from_url(
        url or config.redis_url,
        **redis_connection_kwargs(
            config,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
        ),
    )
    client = Redis(connection_pool=pool)
    record_redis_pool_saturation(client)
    return client


def record_redis_pool_saturation(client: Any, *, pool: str = "default") -> None:
    connection_pool = getattr(client, "connection_pool", None)
    if connection_pool is None:
        return
    _record_pool_saturation(connection_pool, pool=pool)


def _record_pool_saturation(connection_pool: Any, *, pool: str = "default") -> None:
    max_connections = getattr(connection_pool, "max_connections", None)
    if not max_connections:
        return
    in_use = getattr(connection_pool, "_in_use_connections", None)
    if in_use is None:
        in_use_count = 0
    else:
        try:
            in_use_count = len(in_use)
        except TypeError:
            return
    safety_metrics.redis_pool_saturation(pool=pool, value=in_use_count / int(max_connections))


__all__ = ["record_redis_pool_saturation", "redis_connection_kwargs", "redis_from_url"]
