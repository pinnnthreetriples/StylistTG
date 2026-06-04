"""Link account onboarding items to auth batch execution.

Revision ID: 20260604_0059
Revises: 20260602_0058
Create Date: 2026-06-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260604_0059"
down_revision = "20260602_0058"
branch_labels = None
depends_on = None

uuid_string = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")


def upgrade() -> None:
    op.add_column(
        "account_onboarding_item",
        sa.Column("auth_batch_id", uuid_string, nullable=True),
    )
    op.add_column(
        "account_onboarding_item",
        sa.Column("auth_batch_item_id", uuid_string, nullable=True),
    )
    op.add_column(
        "account_onboarding_item",
        sa.Column("phone_number", sa.String(64), nullable=True),
    )
    op.create_foreign_key(
        "fk_account_onboarding_item_auth_batch_id",
        "account_onboarding_item",
        "auth_batch",
        ["auth_batch_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_account_onboarding_item_auth_batch_item_id",
        "account_onboarding_item",
        "auth_batch_item",
        ["auth_batch_item_id"],
        ["id"],
    )
    op.create_index(
        "ix_account_onboarding_item_auth_batch_item",
        "account_onboarding_item",
        ["auth_batch_item_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_account_onboarding_item_auth_batch_item",
        table_name="account_onboarding_item",
    )
    op.drop_constraint(
        "fk_account_onboarding_item_auth_batch_item_id",
        "account_onboarding_item",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_account_onboarding_item_auth_batch_id",
        "account_onboarding_item",
        type_="foreignkey",
    )
    op.drop_column("account_onboarding_item", "auth_batch_item_id")
    op.drop_column("account_onboarding_item", "auth_batch_id")
    op.drop_column("account_onboarding_item", "phone_number")
