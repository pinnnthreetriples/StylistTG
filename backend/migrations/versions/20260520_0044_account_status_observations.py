"""Add account status observations.

Revision ID: 20260520_0044
Revises: 20260520_0043
Create Date: 2026-05-20 00:44:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260520_0044"
down_revision = "20260520_0043"
branch_labels = None
depends_on = None

UUID_STRING = sa.String(length=36).with_variant(postgresql.UUID(as_uuid=False), "postgresql")
DETAILS_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "account_status_observations",
        sa.Column("id", UUID_STRING, nullable=False),
        sa.Column("workspace_id", UUID_STRING, nullable=False),
        sa.Column("account_id", UUID_STRING, nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("proxy_healthy", sa.Boolean(), nullable=False),
        sa.Column("proxy_ip_hash", sa.Text(), nullable=True),
        sa.Column("tdlib_authorized", sa.Boolean(), nullable=False),
        sa.Column("device_model_hash", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_action_taken", sa.String(length=32), nullable=True),
        sa.Column("details_json", DETAILS_JSON, nullable=False, server_default="{}"),
        sa.CheckConstraint(
            "auto_action_taken IS NULL OR auto_action_taken IN ('paused', 'quarantine', 'cooldown', 'none')",
            name="ck_account_status_observations_auto_action",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_account_status_observations_account_observed",
        "account_status_observations",
        ["account_id", "observed_at"],
    )
    op.create_index(
        "ix_account_status_observations_workspace_id",
        "account_status_observations",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_account_status_observations_workspace_id",
        table_name="account_status_observations",
    )
    op.drop_index(
        "ix_account_status_observations_account_observed",
        table_name="account_status_observations",
    )
    op.drop_table("account_status_observations")
