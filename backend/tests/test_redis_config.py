from __future__ import annotations

from app.config import Settings
from app.services import redis_client


def test_redis_connection_kwargs_include_timeouts_keepalive_and_retry() -> None:
    config = Settings(
        _env_file=None,
        redis_socket_timeout_sec=4.5,
        redis_socket_connect_timeout_sec=2.5,
        redis_health_check_interval_sec=15,
        redis_retry_retries=4,
        redis_max_connections=12,
    )

    kwargs = redis_client.redis_connection_kwargs(config)

    assert kwargs["socket_timeout"] == 4.5
    assert kwargs["socket_connect_timeout"] == 2.5
    assert kwargs["socket_keepalive"] is True
    assert kwargs["health_check_interval"] == 15
    assert kwargs["retry_on_timeout"] is True
    assert kwargs["max_connections"] == 12
    assert getattr(kwargs["retry"], "_retries") == 4


def test_redis_from_url_uses_shared_instrumented_pool_without_live_redis(monkeypatch) -> None:
    captured: dict[str, object] = {}
    samples: list[tuple[str, float]] = []

    class FakeMetrics:
        def redis_pool_saturation(self, *, pool: str, value: float) -> None:
            samples.append((pool, value))

    class FakePool:
        max_connections = 4
        _in_use_connections = {object(), object()}

    class FakeRedis:
        def __init__(self, *, connection_pool) -> None:
            self.connection_pool = connection_pool

    def fake_from_url(cls, url: str, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakePool()

    monkeypatch.setattr(redis_client, "safety_metrics", FakeMetrics())
    monkeypatch.setattr(redis_client, "Redis", FakeRedis)
    monkeypatch.setattr(
        redis_client.InstrumentedRedisConnectionPool,
        "from_url",
        classmethod(fake_from_url),
    )

    client = redis_client.redis_from_url(
        "redis://example/0",
        config=Settings(_env_file=None, redis_max_connections=4),
        socket_timeout=0.5,
        socket_connect_timeout=0.25,
    )

    assert isinstance(client, FakeRedis)
    assert captured["url"] == "redis://example/0"
    assert captured["socket_timeout"] == 0.5
    assert captured["socket_connect_timeout"] == 0.25
    assert captured["max_connections"] == 4
    assert samples == [("default", 0.5)]


def test_record_redis_pool_saturation_ignores_clients_without_pool() -> None:
    samples: list[tuple[str, float]] = []

    class FakeMetrics:
        def redis_pool_saturation(self, *, pool: str, value: float) -> None:
            samples.append((pool, value))

    redis_client.record_redis_pool_saturation(object())

    assert samples == []
