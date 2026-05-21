"""Add account terminal status.

Revision ID: 20260520_0048
Revises: 20260520_0047
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260520_0048"
down_revision = "20260520_0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "account",
        sa.Column("terminal_status", sa.String(16), nullable=False, server_default="none"),
    )
    op.create_check_constraint(
        "ck_accounts_terminal_status_valid",
        "account",
        "terminal_status IN ('none','banned','deleted','suspended')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_accounts_terminal_status_valid", "account", type_="check")
    op.drop_column("account", "terminal_status")
