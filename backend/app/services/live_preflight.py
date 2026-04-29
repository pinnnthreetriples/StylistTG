from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sqlalchemy import create_engine, text


@dataclass
class LivePreflightService:
    database_url: str
    redis_ping: Callable[[], bool]
    tdjson_path: Path | None
    tdlib_api_id: str | int | None
    tdlib_api_hash: str | None
    tdlib_database_root: Path
    tdlib_files_root: Path
    worker_expected: bool

    def run(self) -> dict[str, object]:
        tdjson_present = bool(self.tdjson_path and Path(self.tdjson_path).exists())
        tdlib_credentials_present = bool(self.tdlib_api_id and self.tdlib_api_hash)
        postgres_reachable = self._check_database()
        redis_reachable = self._check_redis()
        storage_writable = self._check_storage()
        overall_status = (
            "ok"
            if all(
                [
                    tdjson_present,
                    tdlib_credentials_present,
                    postgres_reachable,
                    redis_reachable,
                    storage_writable,
                ]
            )
            else "degraded"
        )
        return {
            "tdjson_present": tdjson_present,
            "tdlib_credentials_present": tdlib_credentials_present,
            "postgres_reachable": postgres_reachable,
            "redis_reachable": redis_reachable,
            "storage_writable": storage_writable,
            "rq_worker_expected": self.worker_expected,
            "overall_status": overall_status,
        }

    def _check_database(self) -> bool:
        try:
            connect_args = {}
            if self.database_url.startswith("postgresql"):
                connect_args["connect_timeout"] = 3
            engine = create_engine(self.database_url, future=True, connect_args=connect_args)
            with engine.connect() as connection:
                connection.execute(text("select 1"))
            return True
        except Exception:
            return False

    def _check_redis(self) -> bool:
        try:
            return bool(self.redis_ping())
        except Exception:
            return False

    def _check_storage(self) -> bool:
        try:
            self.tdlib_database_root.mkdir(parents=True, exist_ok=True)
            self.tdlib_files_root.mkdir(parents=True, exist_ok=True)
            probe = self.tdlib_files_root / ".preflight-write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except Exception:
            return False
