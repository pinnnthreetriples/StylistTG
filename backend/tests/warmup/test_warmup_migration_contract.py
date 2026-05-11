import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "versions"
    / "20260505_0023_account_preparation_warmup.py"
)


def test_warmup_migration_contract() -> None:
    migration = _load_migration()
    engine = sa.create_engine("sqlite+pysqlite:///:memory:", future=True)

    with engine.begin() as connection:
        _create_required_base_tables(connection)
        migration.op = Operations(MigrationContext.configure(connection))

        migration.upgrade()

        inspector = sa.inspect(connection)
        tables = set(inspector.get_table_names())
        assert {
            "warmup_strategy",
            "warmup_session",
            "warmup_event",
            "warmup_task_run",
        }.issubset(tables)

        assert _column_names(inspector, "warmup_session") >= {
            "id",
            "workspace_id",
            "account_id",
            "strategy_id",
            "status",
            "current_day",
            "next_step_at",
            "last_step_at",
            "cadence_hours",
            "next_attempt_at",
            "consecutive_failures",
        }
        assert _column_names(inspector, "warmup_task_run") >= {
            "session_id",
            "day",
            "task_type",
            "status",
            "metadata_json",
        }

        task_run_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("warmup_task_run")
        }
        assert ("session_id", "day", "task_type") in task_run_uniques

        active_account_index = connection.execute(
            sa.text(
                """
                SELECT sql
                FROM sqlite_master
                WHERE type = 'index'
                  AND name = 'ux_warmup_session_active_account'
                """
            )
        ).scalar_one()
        assert "workspace_id, account_id" in active_account_index
        assert "validating" in active_account_index
        assert "scheduled" in active_account_index
        assert "active" in active_account_index
        assert "paused_risk" in active_account_index
        assert "paused_manual" in active_account_index
        assert "completed" not in active_account_index
        assert "failed" not in active_account_index

        strategy_fks = {
            (fk["referred_table"], tuple(fk["constrained_columns"]))
            for fk in inspector.get_foreign_keys("warmup_strategy")
        }
        session_fks = {
            (fk["referred_table"], tuple(fk["constrained_columns"]))
            for fk in inspector.get_foreign_keys("warmup_session")
        }
        assert ("workspace", ("workspace_id",)) in strategy_fks
        assert ("workspace", ("workspace_id",)) in session_fks
        assert ("account", ("account_id",)) in session_fks

        migration.downgrade()

        remaining_tables = set(sa.inspect(connection).get_table_names())
        assert "warmup_task_run" not in remaining_tables
        assert "warmup_event" not in remaining_tables
        assert "warmup_session" not in remaining_tables
        assert "warmup_strategy" not in remaining_tables


def _load_migration():
    spec = importlib.util.spec_from_file_location("warmup_migration", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.down_revision == "20260503_0022"
    return migration


def _create_required_base_tables(connection: sa.Connection) -> None:
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


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}
