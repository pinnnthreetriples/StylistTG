import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


VERSIONS = Path(__file__).resolve().parents[1] / "migrations" / "versions"
WARMUP_0023 = VERSIONS / "20260505_0023_account_preparation_warmup.py"
ACCOUNT_0024 = VERSIONS / "20260508_0024_account_external_ref_workspace_unique.py"
WARMUP_0025 = VERSIONS / "20260508_0025_warmup_live_foundations.py"


def test_warmup_live_foundations_upgrade_and_downgrade() -> None:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:", future=True)
    with engine.begin() as connection:
        _seed_base_tables(connection)
        _seed_account_proxy(connection)

        _run_migration(WARMUP_0023, connection, "upgrade")
        # 0024 touches account which is unrelated to warmup; we skip it for isolation.
        _run_migration(WARMUP_0025, connection, "upgrade")

        inspector = sa.inspect(connection)
        tables = set(inspector.get_table_names())
        assert {"warmup_trusted_peer", "warmup_isolation_claim"}.issubset(tables)

        strategy_columns = _column_names(inspector, "warmup_strategy")
        assert {
            "execution_mode",
            "preset_kind",
            "duration_days",
            "daily_action_limits_json",
            "session_window_config_json",
            "ui_summary_json",
        }.issubset(strategy_columns)

        session_columns = _column_names(inspector, "warmup_session")
        assert {
            "execution_mode",
            "duration_days",
            "timezone",
            "last_micro_session_at",
            "next_micro_session_at",
            "daily_counters_json",
            "trusted_peer_ids_json",
            "proxy_snapshot_json",
        }.issubset(session_columns)

        proxy_columns = _column_names(inspector, "account_proxy")
        assert "proxy_category" in proxy_columns

        isolation_columns = _column_names(inspector, "warmup_isolation_claim")
        assert {"account_id", "workspace_id", "held_by", "reason", "acquired_at"} == isolation_columns

        trusted_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("warmup_trusted_peer")
        }
        assert ("workspace_id", "account_id") in trusted_uniques

        _run_migration(WARMUP_0025, connection, "downgrade")

        rolled_back = sa.inspect(connection)
        remaining = set(rolled_back.get_table_names())
        assert "warmup_trusted_peer" not in remaining
        assert "warmup_isolation_claim" not in remaining
        assert "proxy_category" not in _column_names(rolled_back, "account_proxy")
        assert "duration_days" not in _column_names(rolled_back, "warmup_strategy")
        assert "duration_days" not in _column_names(rolled_back, "warmup_session")


def _run_migration(path: Path, connection: sa.Connection, direction: str) -> None:
    migration = _load_migration(path)
    migration.op = Operations(MigrationContext.configure(connection))
    getattr(migration, direction)()


def _load_migration(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed_base_tables(connection: sa.Connection) -> None:
    metadata = sa.MetaData()
    sa.Table(
        "workspace",
        metadata,
        sa.Column("id", sa.String(length=36), primary_key=True),
    )
    sa.Table(
        "account",
        metadata,
        sa.Column("id", sa.String(length=36), primary_key=True),
    )
    metadata.create_all(connection)


def _seed_account_proxy(connection: sa.Connection) -> None:
    metadata = sa.MetaData()
    sa.Table(
        "account_proxy",
        metadata,
        sa.Column("account_id", sa.String(length=36), primary_key=True),
        sa.Column("proxy_type", sa.String(length=16), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
    )
    metadata.create_all(connection)


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}
