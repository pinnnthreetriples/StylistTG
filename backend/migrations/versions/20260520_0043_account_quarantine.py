"""Create account quarantine table.

Revision ID: 20260520_0043
Revises: 20260520_0038
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260520_0043"
down_revision = "20260520_0038"
branch_labels = None
depends_on = None

UUID_STRING = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")
METADATA_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "account_quarantines",
        sa.Column("id", UUID_STRING, nullable=False),
        sa.Column("workspace_id", UUID_STRING, nullable=False),
        sa.Column("account_id", UUID_STRING, nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_by_user_id", UUID_STRING, nullable=True),
        sa.Column("metadata_json", METADATA_JSON, nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.ForeignKeyConstraint(["released_by_user_id"], ["app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "reason IN ('flood_wait', 'status_degraded', 'manual', "
            "'bought_rest_period', 'fraud_high')",
            name="ck_account_quarantines_reason",
        ),
    )
    op.create_index(
        "ix_account_quarantines_ws_account_until",
        "account_quarantines",
        ["workspace_id", "account_id", "until"],
    )


def downgrade() -> None:
    op.drop_index("ix_account_quarantines_ws_account_until", table_name="account_quarantines")
    op.drop_table("account_quarantines")
