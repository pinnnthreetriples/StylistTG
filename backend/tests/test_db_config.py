from __future__ import annotations

from app import db


def test_engine_kwargs_add_postgres_pool_and_timeout_settings(monkeypatch) -> None:
    monkeypatch.setattr(db.settings, "db_pool_size", 21)
    monkeypatch.setattr(db.settings, "db_max_overflow", 11)
    monkeypatch.setattr(db.settings, "db_pool_recycle_seconds", 1800)
    monkeypatch.setattr(db.settings, "db_connect_timeout_seconds", 7)
    monkeypatch.setattr(db.settings, "db_query_timeout_ms", 12000)

    kwargs = db.engine_kwargs("postgresql+psycopg://user:pass@localhost/db")

    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_size"] == 21
    assert kwargs["max_overflow"] == 11
    assert kwargs["pool_recycle"] == 1800
    assert kwargs["connect_args"] == {
        "connect_timeout": 7,
        "options": "-c statement_timeout=12000",
    }


def test_engine_kwargs_omits_statement_timeout_startup_option_for_neon_pooler(
    monkeypatch,
) -> None:
    monkeypatch.setattr(db.settings, "db_connect_timeout_seconds", 7)
    monkeypatch.setattr(db.settings, "db_query_timeout_ms", 12000)

    kwargs = db.engine_kwargs(
        "postgresql+psycopg://user:pass@ep-demo-pooler.us-east-1.aws.neon.tech/db"
    )

    assert kwargs["connect_args"] == {"connect_timeout": 7}


def test_engine_kwargs_omits_postgres_only_settings_for_sqlite() -> None:
    kwargs = db.engine_kwargs("sqlite+pysqlite:///:memory:")

    assert kwargs == {"future": True, "pool_pre_ping": True}


def test_record_db_pool_saturation_reports_checked_out_ratio(monkeypatch) -> None:
    samples: list[tuple[str, float]] = []

    class FakeMetrics:
        def db_pool_saturation(self, *, pool: str, value: float) -> None:
            samples.append((pool, value))

    class FakePool:
        def size(self) -> int:
            return 10

        def checkedout(self) -> int:
            return 8

    class FakeEngine:
        pool = FakePool()

    monkeypatch.setattr(db, "safety_metrics", FakeMetrics())

    db._record_db_pool_saturation(FakeEngine())

    assert samples == [("default", 0.8)]
