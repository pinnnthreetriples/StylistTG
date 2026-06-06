import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "migrations"
    / "versions"
    / "20260605_0063_account_survival_metric.py"
)


def test_account_survival_migration_contract() -> None:
    migration = _load_migration()
    engine = sa.create_engine("sqlite+pysqlite:///:memory:", future=True)

    try:
        with engine.begin() as connection:
            _create_required_base_tables(connection)
            migration.op = Operations(MigrationContext.configure(connection))

            migration.upgrade()

            inspector = sa.inspect(connection)
            assert "account_survival_metric" in set(inspector.get_table_names())
            assert _column_names(inspector, "account_survival_metric") >= {
                "id",
                "workspace_id",
                "account_id",
                "imported_at",
                "warmup_started_at",
                "warmup_completed_at",
                "pre_production_at",
                "first_action_after_warmup_at",
                "first_freeze_at",
                "first_unfreeze_at",
                "freeze_count",
                "flood_wait_count",
                "banned_at",
                "deleted_at",
                "survival_days",
            }

            unique_constraints = {
                tuple(constraint["column_names"])
                for constraint in inspector.get_unique_constraints("account_survival_metric")
            }
            assert ("workspace_id", "account_id") in unique_constraints

            banned_index = connection.execute(
                sa.text(
                    """
                    SELECT sql
                    FROM sqlite_master
                    WHERE type = 'index'
                      AND name = 'ix_account_survival_metric_banned_at'
                    """
                )
            ).scalar_one()
            assert "banned_at IS NOT NULL" in banned_index

            migration.downgrade()

            remaining_tables = set(sa.inspect(connection).get_table_names())
            assert "account_survival_metric" not in remaining_tables
    finally:
        engine.dispose()


def _load_migration():
    spec = importlib.util.spec_from_file_location("account_survival_migration", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.down_revision == "20260605_0062"
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
