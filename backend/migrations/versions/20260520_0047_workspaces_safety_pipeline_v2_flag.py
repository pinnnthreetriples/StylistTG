"""Add per-workspace safety pipeline v2 feature flag."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260520_0047"
down_revision = "20260520_0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspace",
        sa.Column(
            "safety_pipeline_v2_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("workspace", "safety_pipeline_v2_enabled")
