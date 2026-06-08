"""Add warmup p2p friend links.

Revision ID: 20260605_0064
Revises: 20260605_0063
Create Date: 2026-06-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260605_0064"
down_revision = "20260605_0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid_string = sa.String(length=36)
    op.create_table(
        "warmup_p2p_friend_link",
        sa.Column("id", uuid_string, primary_key=True, nullable=False),
        sa.Column("workspace_id", uuid_string, sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column(
            "account_id",
            uuid_string,
            sa.ForeignKey("account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "friend_account_id",
            uuid_string,
            sa.ForeignKey("account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("account_id != friend_account_id", name="ck_warmup_p2p_friend_not_self"),
        sa.UniqueConstraint(
            "workspace_id",
            "account_id",
            "friend_account_id",
            name="uq_warmup_p2p_friend_link_pair",
        ),
    )
    op.create_index(
        "ix_warmup_p2p_friend_link_account",
        "warmup_p2p_friend_link",
        ["workspace_id", "account_id"],
    )
    op.create_index(
        "ix_warmup_p2p_friend_link_friend",
        "warmup_p2p_friend_link",
        ["workspace_id", "friend_account_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_warmup_p2p_friend_link_friend", table_name="warmup_p2p_friend_link")
    op.drop_index("ix_warmup_p2p_friend_link_account", table_name="warmup_p2p_friend_link")
    op.drop_table("warmup_p2p_friend_link")
