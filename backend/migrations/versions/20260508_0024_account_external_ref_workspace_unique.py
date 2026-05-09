"""Scope account external_ref uniqueness to workspace."""

from __future__ import annotations

from alembic import op


revision = "20260508_0024"
down_revision = "20260505_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("account_external_ref_key", "account", type_="unique")
    op.create_unique_constraint(
        "uq_account_workspace_external_ref",
        "account",
        ["workspace_id", "external_ref"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_account_workspace_external_ref", "account", type_="unique")
    op.create_unique_constraint("account_external_ref_key", "account", ["external_ref"])
