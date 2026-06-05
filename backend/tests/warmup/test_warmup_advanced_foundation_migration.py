import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


VERSIONS = Path(__file__).resolve().parents[2] / "migrations" / "versions"
WARMUP_0023 = VERSIONS / "20260505_0023_account_preparation_warmup.py"
WARMUP_0025 = VERSIONS / "20260508_0025_warmup_live_foundations.py"
WARMUP_0060 = VERSIONS / "20260605_0060_warmup_channel_state.py"
WARMUP_0061 = VERSIONS / "20260605_0061_warmup_cold_soak_status.py"
WARMUP_0062 = VERSIONS / "20260605_0062_warmup_personality_disabled.py"


def test_warmup_advanced_foundation_upgrade_and_downgrade() -> None:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:", future=True)
    try:
        with engine.begin() as connection:
            _seed_base_tables(connection)
            _seed_account_proxy(connection)

            _run_migration(WARMUP_0023, connection, "upgrade")
            _run_migration(WARMUP_0025, connection, "upgrade")
            _run_migration(WARMUP_0060, connection, "upgrade")
            _run_migration(WARMUP_0061, connection, "upgrade")
            _run_migration(WARMUP_0062, connection, "upgrade")

            inspector = sa.inspect(connection)
            assert "warmup_channel_state" in set(inspector.get_table_names())
            assert _column_names(inspector, "warmup_channel_state") >= {
                "id",
                "workspace_id",
                "account_id",
                "channel_ref",
                "subscribed_at",
                "last_feed_read_at",
                "last_story_view_at",
                "last_react_at",
                "last_browse_at",
                "has_stories",
                "has_reactions",
                "available_reactions_json",
                "health_score",
                "success_count",
                "fail_count",
                "created_at",
                "updated_at",
            }

            channel_uniques = {
                tuple(constraint["column_names"])
                for constraint in inspector.get_unique_constraints("warmup_channel_state")
            }
            assert ("workspace_id", "account_id", "channel_ref") in channel_uniques

            session_columns = _column_names(inspector, "warmup_session")
            assert {
                "cold_soak_until",
                "personality_seed_json",
                "disabled_actions_json",
                "lifecycle_state",
                "strategy_snapshot_json",
            }.issubset(session_columns)

            _assert_insert_defaults(connection)

            _run_migration(WARMUP_0062, connection, "downgrade")
            _run_migration(WARMUP_0061, connection, "downgrade")
            _run_migration(WARMUP_0060, connection, "downgrade")

            rolled_back = sa.inspect(connection)
            assert "warmup_channel_state" not in set(rolled_back.get_table_names())
            rolled_back_session_columns = _column_names(rolled_back, "warmup_session")
            assert "cold_soak_until" not in rolled_back_session_columns
            assert "personality_seed_json" not in rolled_back_session_columns
            assert "disabled_actions_json" not in rolled_back_session_columns
            assert "lifecycle_state" not in rolled_back_session_columns
            assert "strategy_snapshot_json" not in rolled_back_session_columns
    finally:
        engine.dispose()


def _assert_insert_defaults(connection: sa.Connection) -> None:
    connection.execute(sa.text("INSERT INTO workspace (id) VALUES ('workspace-1')"))
    connection.execute(sa.text("INSERT INTO account (id) VALUES ('account-1')"))
    connection.execute(
        sa.text(
            """
            INSERT INTO warmup_strategy (
                id,
                workspace_id,
                name,
                tier_limits_json,
                target_channels_json
            )
            VALUES (
                'strategy-1',
                'workspace-1',
                'Advanced',
                '{}',
                '[]'
            )
            """
        )
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO warmup_session (
                id,
                workspace_id,
                account_id,
                strategy_id,
                status,
                current_day,
                cadence_hours,
                flood_wait_count,
                consecutive_failures
            )
            VALUES (
                'session-1',
                'workspace-1',
                'account-1',
                'strategy-1',
                'cold_soak',
                0,
                24,
                0,
                0
            )
            """
        )
    )
    row = connection.execute(
        sa.text(
            """
            SELECT
                personality_seed_json,
                disabled_actions_json,
                lifecycle_state,
                strategy_snapshot_json
            FROM warmup_session
            WHERE id = 'session-1'
            """
        )
    ).mappings().one()

    assert row["personality_seed_json"] == "{}"
    assert row["disabled_actions_json"] == "[]"
    assert row["lifecycle_state"] == "warming"
    assert row["strategy_snapshot_json"] is None


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
