from pathlib import Path

from app.services.live_preflight import LivePreflightService


class FakeRedis:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok

    def ping(self) -> bool:
        if not self.ok:
            raise RuntimeError("redis down")
        return True


def test_live_preflight_returns_structured_result(tmp_path: Path) -> None:
    db_file = tmp_path / "preflight.db"
    db_file.write_text("", encoding="utf-8")
    tdjson = tmp_path / "tdjson.dll"
    tdjson.write_text("stub", encoding="utf-8")
    tdlib_db_root = tmp_path / "tdlib-db"
    tdlib_files_root = tmp_path / "tdlib-files"

    service = LivePreflightService(
        database_url=f"sqlite:///{db_file.as_posix()}",
        redis_ping=lambda: FakeRedis(ok=True).ping(),
        tdjson_path=tdjson,
        tdlib_api_id="123",
        tdlib_api_hash="hash",
        tdlib_database_root=tdlib_db_root,
        tdlib_files_root=tdlib_files_root,
        worker_expected=True,
    )

    result = service.run()

    assert result["tdjson_present"] is True
    assert result["tdlib_credentials_present"] is True
    assert result["postgres_reachable"] is True
    assert result["redis_reachable"] is True
    assert result["storage_writable"] is True
    assert result["overall_status"] == "ok"


def test_live_preflight_reports_degraded_dependencies(tmp_path: Path) -> None:
    service = LivePreflightService(
        database_url=f"sqlite:///{(tmp_path / 'preflight.db').as_posix()}",
        redis_ping=lambda: FakeRedis(ok=False).ping(),
        tdjson_path=tmp_path / "missing.dll",
        tdlib_api_id=None,
        tdlib_api_hash=None,
        tdlib_database_root=tmp_path / "tdlib-db",
        tdlib_files_root=tmp_path / "tdlib-files",
        worker_expected=False,
    )

    result = service.run()

    assert result["tdjson_present"] is False
    assert result["tdlib_credentials_present"] is False
    assert result["redis_reachable"] is False
    assert result["overall_status"] == "degraded"
