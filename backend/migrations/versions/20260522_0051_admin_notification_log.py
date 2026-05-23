"""Add admin notification log and workspace webhook URL.

Revision ID: 20260522_0051
Revises: 20260521_0050
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

UUID_STRING = sa.String(36).with_variant(sa.Uuid(as_uuid=False), "postgresql")

revision = "20260522_0051"
down_revision = "20260521_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspace",
        sa.Column("notification_webhook_url", sa.String(512), nullable=True),
    )
    op.create_table(
        "admin_notification_log",
        sa.Column("id", UUID_STRING, primary_key=True),
        sa.Column("workspace_id", UUID_STRING, sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("trigger_code", sa.String(64), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "metadata_json",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "delivered_channels",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="[]",
        ),
        sa.Index(
            "ix_admin_notification_log_ws_trigger_time",
            "workspace_id",
            "trigger_code",
            "triggered_at",
        ),
    )


def downgrade() -> None:
    op.drop_table("admin_notification_log")
    op.drop_column("workspace", "notification_webhook_url")
