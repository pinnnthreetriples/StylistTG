from __future__ import annotations

import json
from typing import Any, cast

from redis import Redis

from app.config import settings
from app.services.live_preflight import LivePreflightService


def _redis_ping() -> bool:
    return bool(cast(Any, Redis).from_url(settings.redis_url).ping())


def main() -> int:
    service = LivePreflightService(
        database_url=settings.database_url,
        redis_ping=_redis_ping,
        tdjson_path=settings.tdlib_shared_library_path,
        tdlib_api_id=settings.tdlib_api_id,
        tdlib_api_hash=settings.tdlib_api_hash,
        tdlib_database_root=settings.tdlib_database_root,
        tdlib_files_root=settings.tdlib_files_root,
        worker_expected=True,
    )
    result = service.run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["overall_status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
