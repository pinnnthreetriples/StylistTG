from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260519_0031_neuro_comment_channel_rule_unique.py"
)


def test_channel_rule_unique_constraint_migration_deduplicates_existing_rows() -> None:
    migration = _load_migration()
    engine = sa.create_engine("sqlite+pysqlite:///:memory:", future=True)

    try:
        with engine.begin() as connection:
            _create_channel_rules_table(connection)
            connection.execute(
                sa.text(
                    """
                    INSERT INTO neuro_comment_channel_rules
                        (id, workspace_id, target_ref, rule_type, reason, created_by, created_at)
                    VALUES
                        ('older', 'workspace-1', '@target', 'blacklist', NULL, NULL, '2026-05-19 10:00:00'),
                        ('newer', 'workspace-1', '@target', 'blacklist', NULL, NULL, '2026-05-19 10:01:00'),
                        ('other-type', 'workspace-1', '@target', 'whitelist', NULL, NULL, '2026-05-19 10:02:00')
                    """
                )
            )
            migration.op = Operations(MigrationContext.configure(connection))

            migration.upgrade()

            inspector = sa.inspect(connection)
            unique_columns = {
                tuple(constraint["column_names"])
                for constraint in inspector.get_unique_constraints("neuro_comment_channel_rules")
            }
            remaining_ids = {
                row[0]
                for row in connection.execute(
                    sa.text("SELECT id FROM neuro_comment_channel_rules")
                ).all()
            }

            assert ("workspace_id", "target_ref", "rule_type") in unique_columns
            assert remaining_ids == {"newer", "other-type"}

            migration.downgrade()

            rolled_back_uniques = {
                tuple(constraint["column_names"])
                for constraint in sa.inspect(connection).get_unique_constraints(
                    "neuro_comment_channel_rules"
                )
            }
            assert ("workspace_id", "target_ref", "rule_type") not in rolled_back_uniques
    finally:
        engine.dispose()


def _load_migration():
    spec = importlib.util.spec_from_file_location("channel_rule_unique_migration", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "20260519_0030"
    return migration


def _create_channel_rules_table(connection: sa.Connection) -> None:
    metadata = sa.MetaData()
    sa.Table(
        "neuro_comment_channel_rules",
        metadata,
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("target_ref", sa.String(length=255), nullable=False),
        sa.Column("rule_type", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    metadata.create_all(connection)
