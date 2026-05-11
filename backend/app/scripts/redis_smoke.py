from __future__ import annotations

import argparse
import uuid
from collections.abc import Callable
from typing import Any, Protocol, cast

from redis import Redis

from app.scripts.common import (
    CheckReport,
    add_common_json_arg,
    env_value,
    main_guard,
    print_and_exit,
    require_not_production,
    sanitized_url,
)


def _redis_from_url(url: str) -> RedisClient:
    from_url = cast(Callable[[str], object], getattr(cast(Any, Redis), "from_url"))
    return cast(RedisClient, from_url(url))


class RedisClient(Protocol):
    def ping(self) -> object: ...

    def set(self, name: str, value: str, *, ex: int) -> object: ...

    def get(self, name: str) -> str | bytes | None: ...

    def delete(self, name: str) -> object: ...


class RedisClientFactory(Protocol):
    def __call__(self, url: str) -> RedisClient: ...


def run_redis_smoke(
    *,
    allow_production: bool = False,
    env: dict[str, str] | None = None,
    client_factory: RedisClientFactory = _redis_from_url,
) -> CheckReport:
    report = CheckReport("redis_smoke")
    if not require_not_production(report, allow_production=allow_production, env=env):
        return report
    redis_url = env_value("REDIS_URL", env)
    if not redis_url:
        report.add("redis_url", "FAIL", "REDIS_URL is required")
        return report
    if not redis_url.startswith("rediss://"):
        report.add(
            "redis_tls",
            "WARN",
            "rediss:// is preferred for cloud Redis",
            url=sanitized_url(redis_url),
        )
    key = f"smoke:stylisttg:{uuid.uuid4()}"
    try:
        client = client_factory(redis_url)
        client.ping()
        client.set(key, "ok", ex=60)
        value = client.get(key)
        client.delete(key)
        deleted_value = client.get(key)
    except Exception as exc:
        report.add(
            "redis_ping",
            "FAIL",
            "Redis smoke failed",
            url=sanitized_url(redis_url),
            error=type(exc).__name__,
        )
        return report
    if value not in {"ok", b"ok"} or deleted_value is not None:
        report.add("redis_roundtrip", "FAIL", "Redis temporary key roundtrip failed")
    else:
        report.add(
            "redis_roundtrip",
            "PASS",
            "Redis ping/set/get/delete smoke passed",
            url=sanitized_url(redis_url),
            key_prefix="smoke:stylisttg",
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe Redis dev/staging smoke check.")
    parser.add_argument("--allow-production", action="store_true")
    add_common_json_arg(parser)
    args = parser.parse_args()
    print_and_exit(run_redis_smoke(allow_production=args.allow_production), json_output=args.json)


if __name__ == "__main__":
    main_guard(main)
