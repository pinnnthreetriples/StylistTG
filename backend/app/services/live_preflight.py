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
    worker_status: Callable[[], str] | None = None
    profile_worker_status: Callable[[], str] | None = None
    auth_worker_status: Callable[[], str] | None = None

    def run(self) -> dict[str, object]:
        tdjson_present = bool(self.tdjson_path and Path(self.tdjson_path).exists())
        tdlib_credentials_present = bool(self.tdlib_api_id and self.tdlib_api_hash)
        postgres_reachable = self._check_database()
        redis_reachable = self._check_redis()
        storage_writable = self._check_storage()
        profile_worker_status = self._check_worker(redis_reachable, self.profile_worker_status or self.worker_status)
        auth_worker_status = self._check_worker(redis_reachable, self.auth_worker_status or self.worker_status)
        rq_worker_status = _combined_worker_status(profile_worker_status, auth_worker_status)
        overall_status = (
            "ok"
            if all(
                [
                    tdjson_present,
                    tdlib_credentials_present,
                    postgres_reachable,
                    redis_reachable,
                    storage_writable,
                    not self.worker_expected or rq_worker_status == "ready",
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
            "rq_worker_status": rq_worker_status,
            "profile_worker_status": profile_worker_status,
            "auth_worker_status": auth_worker_status,
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

    def _check_worker(self, redis_reachable: bool, worker_status: Callable[[], str] | None) -> str | None:
        if not self.worker_expected:
            return None
        if not redis_reachable or not worker_status:
            return "unknown"
        try:
            status = worker_status()
        except Exception:
            return "unknown"
        if status in {"ready", "missing"}:
            return status
        return "unknown"


def _combined_worker_status(profile_status: str | None, auth_status: str | None) -> str | None:
    if profile_status is None and auth_status is None:
        return None
    if profile_status == "ready" and auth_status == "ready":
        return "ready"
    if profile_status == "missing" or auth_status == "missing":
        return "missing"
    return "unknown"
