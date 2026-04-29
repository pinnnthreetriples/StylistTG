from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260424_0007"
down_revision: str | None = "20260424_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_STRING = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")


def upgrade() -> None:
    op.create_table(
        "account_story_draft",
        sa.Column("id", UUID_STRING, primary_key=True),
        sa.Column("account_id", UUID_STRING, sa.ForeignKey("account.id"), nullable=False),
        sa.Column("asset_id", UUID_STRING, nullable=False),
        sa.Column("media_kind", sa.String(length=32), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("privacy_preset", sa.String(length=64), nullable=False, server_default="contacts"),
        sa.Column("active_period_seconds", sa.Integer(), nullable=False, server_default="86400"),
        sa.Column("protect_content", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("validation_status", sa.String(length=64), nullable=False, server_default="ready"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_account_story_draft_account_id_created_at", "account_story_draft", ["account_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_account_story_draft_account_id_created_at", table_name="account_story_draft")
    op.drop_table("account_story_draft")
