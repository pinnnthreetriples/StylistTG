"""Workspace-scope account safety overrides.

Revision ID: 20260526_0056
Revises: 20260525_0054
Create Date: 2026-05-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260526_0056"
down_revision = "20260525_0054"
branch_labels = None
depends_on = None


TABLE_NAME = "account_safety_override"
WORKSPACE_INDEX = "ix_account_safety_override_workspace_id"
WORKSPACE_COMPOSITE_INDEX = "ix_override_workspace_account_op_until"
WORKSPACE_FK = "account_safety_override_workspace_id_fkey"
DEFAULT_WORKSPACE_ID = "00000000-0000-4000-8000-000000000001"
WORKSPACE_ID_TYPE = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")


def upgrade() -> None:
    op.add_column(
        TABLE_NAME,
        sa.Column(
            "workspace_id",
            WORKSPACE_ID_TYPE,
            nullable=True,
        ),
    )
    # expected: requires online schema change
    op.execute(
        """
        UPDATE account_safety_override aso
        SET workspace_id = account.workspace_id
        FROM account
        WHERE aso.account_id = account.id
        """
    )
    null_count = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM account_safety_override WHERE workspace_id IS NULL")
    )
    if null_count:
        raise RuntimeError("account_safety_override.workspace_id backfill left NULL rows")

    op.create_index(WORKSPACE_INDEX, TABLE_NAME, ["workspace_id"])
    op.create_index(
        WORKSPACE_COMPOSITE_INDEX,
        TABLE_NAME,
        ["workspace_id", "account_id", "operation", "allowed_until"],
    )
    op.create_foreign_key(
        WORKSPACE_FK,
        TABLE_NAME,
        "workspace",
        ["workspace_id"],
        ["id"],
    )
    op.alter_column(
        TABLE_NAME,
        "workspace_id",
        existing_type=WORKSPACE_ID_TYPE,
        nullable=False,
        server_default=DEFAULT_WORKSPACE_ID,
    )
    op.alter_column(
        TABLE_NAME,
        "workspace_id",
        existing_type=WORKSPACE_ID_TYPE,
        server_default=None,
    )


def downgrade() -> None:
    op.drop_constraint(WORKSPACE_FK, TABLE_NAME, type_="foreignkey")
    op.drop_index(WORKSPACE_COMPOSITE_INDEX, table_name=TABLE_NAME)
    op.drop_index(WORKSPACE_INDEX, table_name=TABLE_NAME)
    op.drop_column(TABLE_NAME, "workspace_id")
