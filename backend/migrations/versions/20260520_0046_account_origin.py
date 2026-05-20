"""Add account origin and bought onboarding state.

Revision ID: 20260520_0046
Revises: 20260520_0045
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260520_0046"
down_revision = "20260520_0045"
branch_labels = None
depends_on = None

UUID_STRING = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")
DETAILS_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column(
        "account",
        sa.Column("origin", sa.String(16), nullable=False, server_default="imported"),
    )
    op.create_check_constraint(
        "ck_accounts_origin_valid",
        "account",
        "origin IN ('imported','bought','created')",
    )
    op.create_table(
        "bought_onboarding_state",
        sa.Column("id", UUID_STRING, nullable=False),
        sa.Column("workspace_id", UUID_STRING, nullable=False),
        sa.Column("account_id", UUID_STRING, nullable=False),
        sa.Column(
            "current_step",
            sa.String(length=64),
            nullable=False,
            server_default="enable_2fa",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details_json", DETAILS_JSON, nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "account_id",
            name="uq_bought_onboarding_state_ws_account",
        ),
        sa.CheckConstraint(
            "current_step IN ('enable_2fa','terminate_other_sessions','rest_period',"
            "'ggr_precheck','completed')",
            name="ck_bought_onboarding_state_current_step",
        ),
    )
    op.create_index(
        "ix_bought_onboarding_state_workspace_account",
        "bought_onboarding_state",
        ["workspace_id", "account_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bought_onboarding_state_workspace_account",
        table_name="bought_onboarding_state",
    )
    op.drop_table("bought_onboarding_state")
    op.drop_constraint("ck_accounts_origin_valid", "account", type_="check")
    op.drop_column("account", "origin")
