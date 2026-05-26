"""Add active quarantine uniqueness guard.

Revision ID: 20260526_0055
Revises: 20260525_0054
Create Date: 2026-05-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260526_0055"
down_revision = "20260525_0054"
branch_labels = None
depends_on = None


INDEX_NAME = "uq_account_quarantine_active"
TABLE_NAME = "account_quarantines"


def upgrade() -> None:
    # expected: requires online schema change
    op.create_index(
        INDEX_NAME,
        TABLE_NAME,
        ["workspace_id", "account_id"],
        unique=True,
        postgresql_where=sa.text("released_at IS NULL"),
        sqlite_where=sa.text("released_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
