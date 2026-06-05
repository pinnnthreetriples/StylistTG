"""Add account survival metrics.

Revision ID: 20260605_0063
Revises: 20260605_0062
Create Date: 2026-06-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260605_0063"
down_revision = "20260605_0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    uuid_string = sa.String(length=36)
    survival_days = (
        sa.Column(
            "survival_days",
            sa.Integer(),
            sa.Computed(
                "GREATEST(0, FLOOR(EXTRACT(EPOCH FROM "
                "(COALESCE(banned_at, deleted_at, updated_at) - imported_at)) / 86400))",
                persisted=True,
            ),
            nullable=True,
        )
        if bind.dialect.name == "postgresql"
        else sa.Column(
            "survival_days",
            sa.Integer(),
            sa.Computed(
                "CAST(julianday(COALESCE(banned_at, deleted_at, updated_at)) - "
                "julianday(imported_at) AS INTEGER)"
            ),
            nullable=True,
        )
    )
    op.create_table(
        "account_survival_metric",
        sa.Column("id", uuid_string, primary_key=True, nullable=False),
        sa.Column("workspace_id", uuid_string, sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column(
            "account_id",
            uuid_string,
            sa.ForeignKey("account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("warmup_strategy_id", uuid_string, nullable=True),
        sa.Column("warmup_strategy_name", sa.String(length=128), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("warmup_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("warmup_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pre_production_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_action_after_warmup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_freeze_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_unfreeze_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("freeze_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("flood_wait_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        survival_days,
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "workspace_id",
            "account_id",
            name="uq_account_survival_metric_workspace_account",
        ),
        sa.CheckConstraint("freeze_count >= 0", name="ck_account_survival_freeze_count"),
        sa.CheckConstraint(
            "flood_wait_count >= 0", name="ck_account_survival_flood_wait_count"
        ),
    )
    op.create_index(
        "ix_account_survival_metric_workspace_id",
        "account_survival_metric",
        ["workspace_id"],
    )
    op.create_index(
        "ix_account_survival_metric_account_id",
        "account_survival_metric",
        ["account_id"],
    )
    op.create_index(
        "ix_account_survival_metric_banned_at",
        "account_survival_metric",
        ["banned_at"],
        postgresql_where=sa.text("banned_at IS NOT NULL"),
        sqlite_where=sa.text("banned_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_account_survival_metric_banned_at", table_name="account_survival_metric")
    op.drop_index("ix_account_survival_metric_account_id", table_name="account_survival_metric")
    op.drop_index(
        "ix_account_survival_metric_workspace_id", table_name="account_survival_metric"
    )
    op.drop_table("account_survival_metric")
