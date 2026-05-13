"""persist runtime settings

Revision ID: 20260512_0028
Revises: 20260510_0027
Create Date: 2026-05-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260512_0028"
down_revision: str | None = "20260510_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runtime_setting",
        sa.Column("key", sa.String(length=128), primary_key=True),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("runtime_setting")
