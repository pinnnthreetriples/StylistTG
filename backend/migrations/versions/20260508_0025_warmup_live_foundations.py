"""Warmup live engine foundations: duration_days, execution_mode, preset_kind, trusted peers, isolation claims."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "20260508_0025"
down_revision = "20260508_0024"
branch_labels = None
depends_on = None


uuid_string = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")
json_type = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    _extend_warmup_strategy()
    _extend_warmup_session()
    _extend_warmup_task_run()
    _extend_account_proxy()
    _create_warmup_trusted_peer()
    _create_warmup_isolation_claim()


def _extend_warmup_strategy() -> None:
    with op.batch_alter_table("warmup_strategy") as batch_op:
        batch_op.add_column(
            sa.Column(
                "execution_mode",
                sa.String(length=32),
                nullable=False,
                server_default="dry_run",
            )
        )
        batch_op.add_column(
            sa.Column(
                "preset_kind",
                sa.String(length=32),
                nullable=False,
                server_default="custom",
            )
        )
        batch_op.add_column(
            sa.Column(
                "duration_days",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("14"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "daily_action_limits_json",
                json_type,
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "session_window_config_json",
                json_type,
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "ui_summary_json",
                json_type,
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
        batch_op.create_check_constraint(
            "ck_warmup_strategy_execution_mode",
            "execution_mode IN ('dry_run', 'shadow', 'passive', 'network', 'advanced')",
        )
        batch_op.create_check_constraint(
            "ck_warmup_strategy_preset_kind",
            "preset_kind IN ('express', 'standard', 'hardened', 'custom')",
        )
        batch_op.create_check_constraint(
            "ck_warmup_strategy_duration_days",
            "duration_days BETWEEN 3 AND 30",
        )


def _extend_warmup_session() -> None:
    with op.batch_alter_table("warmup_session") as batch_op:
        batch_op.add_column(
            sa.Column(
                "execution_mode",
                sa.String(length=32),
                nullable=False,
                server_default="dry_run",
            )
        )
        batch_op.add_column(
            sa.Column(
                "duration_days",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("14"),
            )
        )
        batch_op.add_column(sa.Column("timezone", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("last_micro_session_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("next_micro_session_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "daily_counters_json",
                json_type,
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "trusted_peer_ids_json",
                json_type,
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )
        batch_op.add_column(sa.Column("proxy_snapshot_json", json_type, nullable=True))
        batch_op.drop_constraint("ck_warmup_session_current_day", type_="check")
        batch_op.create_check_constraint(
            "ck_warmup_session_current_day",
            "current_day BETWEEN 0 AND 30",
        )
        batch_op.create_check_constraint(
            "ck_warmup_session_duration_days",
            "duration_days BETWEEN 3 AND 30",
        )


def _extend_warmup_task_run() -> None:
    with op.batch_alter_table("warmup_task_run") as batch_op:
        batch_op.drop_constraint("ck_warmup_task_run_day", type_="check")
        batch_op.create_check_constraint(
            "ck_warmup_task_run_day",
            "day BETWEEN 0 AND 30",
        )


def _extend_account_proxy() -> None:
    with op.batch_alter_table("account_proxy") as batch_op:
        batch_op.add_column(
            sa.Column(
                "proxy_category",
                sa.String(length=16),
                nullable=False,
                server_default="unknown",
            )
        )


def _create_warmup_trusted_peer() -> None:
    op.create_table(
        "warmup_trusted_peer",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("account_id", uuid_string, nullable=False),
        sa.Column("eligible_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "max_active_contacts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("3"),
        ),
        sa.Column(
            "current_contacts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspace.id"], name="fk_warmup_trusted_peer_workspace_id"
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name="fk_warmup_trusted_peer_account_id"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_warmup_trusted_peer"),
        sa.UniqueConstraint(
            "workspace_id", "account_id", name="uq_warmup_trusted_peer_workspace_account"
        ),
        sa.CheckConstraint(
            "max_active_contacts >= 0",
            name="ck_warmup_trusted_peer_max_active_contacts",
        ),
        sa.CheckConstraint(
            "current_contacts >= 0",
            name="ck_warmup_trusted_peer_current_contacts",
        ),
    )
    op.create_index(
        "ix_warmup_trusted_peer_workspace_eligible",
        "warmup_trusted_peer",
        ["workspace_id", "eligible_from"],
    )


def _create_warmup_isolation_claim() -> None:
    op.create_table(
        "warmup_isolation_claim",
        sa.Column("account_id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("held_by", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column(
            "acquired_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name="fk_warmup_isolation_claim_account_id"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspace.id"], name="fk_warmup_isolation_claim_workspace_id"
        ),
        sa.PrimaryKeyConstraint("account_id", name="pk_warmup_isolation_claim"),
    )


def downgrade() -> None:
    op.drop_table("warmup_isolation_claim")
    op.drop_index("ix_warmup_trusted_peer_workspace_eligible", table_name="warmup_trusted_peer")
    op.drop_table("warmup_trusted_peer")

    with op.batch_alter_table("account_proxy") as batch_op:
        batch_op.drop_column("proxy_category")

    with op.batch_alter_table("warmup_task_run") as batch_op:
        batch_op.drop_constraint("ck_warmup_task_run_day", type_="check")
        batch_op.create_check_constraint(
            "ck_warmup_task_run_day",
            "day BETWEEN 0 AND 14",
        )

    with op.batch_alter_table("warmup_session") as batch_op:
        batch_op.drop_constraint("ck_warmup_session_duration_days", type_="check")
        batch_op.drop_constraint("ck_warmup_session_current_day", type_="check")
        batch_op.create_check_constraint(
            "ck_warmup_session_current_day",
            "current_day BETWEEN 0 AND 14",
        )
        batch_op.drop_column("proxy_snapshot_json")
        batch_op.drop_column("trusted_peer_ids_json")
        batch_op.drop_column("daily_counters_json")
        batch_op.drop_column("next_micro_session_at")
        batch_op.drop_column("last_micro_session_at")
        batch_op.drop_column("timezone")
        batch_op.drop_column("duration_days")
        batch_op.drop_column("execution_mode")

    with op.batch_alter_table("warmup_strategy") as batch_op:
        batch_op.drop_constraint("ck_warmup_strategy_duration_days", type_="check")
        batch_op.drop_constraint("ck_warmup_strategy_preset_kind", type_="check")
        batch_op.drop_constraint("ck_warmup_strategy_execution_mode", type_="check")
        batch_op.drop_column("ui_summary_json")
        batch_op.drop_column("session_window_config_json")
        batch_op.drop_column("daily_action_limits_json")
        batch_op.drop_column("duration_days")
        batch_op.drop_column("preset_kind")
        batch_op.drop_column("execution_mode")
