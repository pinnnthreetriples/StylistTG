"""Create account_ggr_scores table.

Phase 2 Task 11: GGR Calculator — composite 1.0–10.0 account survivability
rating. Stores per-account GGR score, bucket, component breakdown, and
scheduling metadata for periodic recalculation.

Revision ID: 20260520_0036
Revises: 20260520_0035
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260520_0036"
down_revision = "20260520_0035"
branch_labels = None
depends_on = None

UUID_STRING = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")


def upgrade() -> None:
    op.create_table(
        "account_ggr_scores",
        sa.Column("id", UUID_STRING, nullable=False),
        sa.Column("workspace_id", UUID_STRING, nullable=False),
        sa.Column("account_id", UUID_STRING, nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="5.0"),
        sa.Column(
            "bucket",
            sa.String(length=16),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("breakdown_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "previous_score", sa.Float(), nullable=True
        ),
        sa.Column(
            "next_calculation_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_calculated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
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
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "account_id", name="uq_account_ggr_scores_ws_account"),
        sa.CheckConstraint("score >= 1.0 AND score <= 10.0", name="ck_account_ggr_scores_range"),
        sa.CheckConstraint(
            "bucket IN ('strong', 'medium', 'weak')",
            name="ck_account_ggr_scores_bucket",
        ),
    )
    op.create_index(
        "ix_account_ggr_scores_workspace_id",
        "account_ggr_scores",
        ["workspace_id"],
    )
    op.create_index(
        "ix_account_ggr_scores_account_id",
        "account_ggr_scores",
        ["account_id"],
    )
    op.create_index(
        "ix_account_ggr_scores_next_calculation",
        "account_ggr_scores",
        ["next_calculation_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_account_ggr_scores_next_calculation", table_name="account_ggr_scores")
    op.drop_index("ix_account_ggr_scores_account_id", table_name="account_ggr_scores")
    op.drop_index("ix_account_ggr_scores_workspace_id", table_name="account_ggr_scores")
    op.drop_table("account_ggr_scores")
