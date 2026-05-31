"""Add account preparation warmup foundation."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "20260505_0023"
down_revision = "20260503_0022"
branch_labels = None
depends_on = None


uuid_string = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")
json_type = sa.JSON().with_variant(JSONB(), "postgresql")

SESSION_STATUSES = (
    "'draft'",
    "'validating'",
    "'scheduled'",
    "'active'",
    "'paused_risk'",
    "'paused_manual'",
    "'completed'",
    "'failed'",
)
TASK_RUN_STATUSES = ("'started'", "'completed'", "'skipped'", "'failed'")


def upgrade() -> None:
    _create_warmup_strategy()
    _create_warmup_session()
    _create_warmup_event()
    _create_warmup_task_run()


def _create_warmup_strategy() -> None:
    op.create_table(
        "warmup_strategy",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tier_limits_json", json_type, nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "target_channels_json", json_type, nullable=False, server_default=sa.text("'[]'")
        ),
        sa.Column("is_preset", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspace.id"], name="fk_warmup_strategy_workspace_id"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_warmup_strategy"),
        sa.UniqueConstraint("workspace_id", "name", name="uq_warmup_strategy_workspace_name"),
    )
    op.create_index("ix_warmup_strategy_workspace_id", "warmup_strategy", ["workspace_id"])
    op.create_index("ix_warmup_strategy_preset", "warmup_strategy", ["is_preset"])


def _create_warmup_session() -> None:
    op.create_table(
        "warmup_session",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("account_id", uuid_string, nullable=False),
        sa.Column("strategy_id", uuid_string, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("current_day", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cadence_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("next_step_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_step_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("flood_wait_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            f"status IN ({', '.join(SESSION_STATUSES)})",
            name="ck_warmup_session_status",
        ),
        sa.CheckConstraint("current_day BETWEEN 0 AND 14", name="ck_warmup_session_current_day"),
        sa.CheckConstraint("cadence_hours >= 1", name="ck_warmup_session_cadence_hours"),
        sa.CheckConstraint("flood_wait_count >= 0", name="ck_warmup_session_flood_wait_count"),
        sa.CheckConstraint(
            "consecutive_failures >= 0",
            name="ck_warmup_session_consecutive_failures",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name="fk_warmup_session_account_id"
        ),
        sa.ForeignKeyConstraint(
            ["strategy_id"], ["warmup_strategy.id"], name="fk_warmup_session_strategy_id"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspace.id"], name="fk_warmup_session_workspace_id"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_warmup_session"),
    )
    op.create_index("ix_warmup_session_workspace_id", "warmup_session", ["workspace_id"])
    op.create_index("ix_warmup_session_account_id", "warmup_session", ["account_id"])
    op.create_index("ix_warmup_session_status", "warmup_session", ["status"])
    op.create_index(
        "ix_warmup_session_due",
        "warmup_session",
        ["next_step_at"],
        postgresql_where=sa.text("status IN ('scheduled', 'active')"),
        sqlite_where=sa.text("status IN ('scheduled', 'active')"),
    )
    op.create_index(
        "ux_warmup_session_active_account",
        "warmup_session",
        ["workspace_id", "account_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('validating', 'scheduled', 'active', 'paused_risk', 'paused_manual')"
        ),
        sqlite_where=sa.text(
            "status IN ('validating', 'scheduled', 'active', 'paused_risk', 'paused_manual')"
        ),
    )


def _create_warmup_event() -> None:
    op.create_table(
        "warmup_event",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("session_id", uuid_string, nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", json_type, nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["warmup_session.id"], name="fk_warmup_event_session_id"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspace.id"], name="fk_warmup_event_workspace_id"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_warmup_event"),
    )
    op.create_index("ix_warmup_event_workspace_id", "warmup_event", ["workspace_id"])
    op.create_index("ix_warmup_event_session_created", "warmup_event", ["session_id", "created_at"])


def _create_warmup_task_run() -> None:
    op.create_table(
        "warmup_task_run",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("session_id", uuid_string, nullable=False),
        sa.Column("day", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", json_type, nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("day BETWEEN 0 AND 14", name="ck_warmup_task_run_day"),
        sa.CheckConstraint(
            f"status IN ({', '.join(TASK_RUN_STATUSES)})",
            name="ck_warmup_task_run_status",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["warmup_session.id"], name="fk_warmup_task_run_session_id"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspace.id"], name="fk_warmup_task_run_workspace_id"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_warmup_task_run"),
        sa.UniqueConstraint(
            "session_id", "day", "task_type", name="uq_warmup_task_run_session_day_type"
        ),
    )
    op.create_index("ix_warmup_task_run_workspace_id", "warmup_task_run", ["workspace_id"])
    op.create_index("ix_warmup_task_run_session_id", "warmup_task_run", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_warmup_task_run_session_id", table_name="warmup_task_run")
    op.drop_index("ix_warmup_task_run_workspace_id", table_name="warmup_task_run")
    op.drop_table("warmup_task_run")
    op.drop_index("ix_warmup_event_session_created", table_name="warmup_event")
    op.drop_index("ix_warmup_event_workspace_id", table_name="warmup_event")
    op.drop_table("warmup_event")
    op.drop_index("ux_warmup_session_active_account", table_name="warmup_session")
    op.drop_index("ix_warmup_session_due", table_name="warmup_session")
    op.drop_index("ix_warmup_session_status", table_name="warmup_session")
    op.drop_index("ix_warmup_session_account_id", table_name="warmup_session")
    op.drop_index("ix_warmup_session_workspace_id", table_name="warmup_session")
    op.drop_table("warmup_session")
    op.drop_index("ix_warmup_strategy_preset", table_name="warmup_strategy")
    op.drop_index("ix_warmup_strategy_workspace_id", table_name="warmup_strategy")
    op.drop_table("warmup_strategy")
