from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260424_0005"
down_revision: str | None = "20260424_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_STRING = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")


def upgrade() -> None:
    op.create_table(
        "account_profile_audio_state",
        sa.Column("account_id", UUID_STRING, sa.ForeignKey("account.id"), primary_key=True),
        sa.Column("telegram_audio_id", sa.String(length=255), nullable=True),
        sa.Column("telegram_file_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("performer", sa.String(length=255), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("mime", sa.String(length=128), nullable=True),
        sa.Column("source_asset_id", UUID_STRING, nullable=True),
        sa.Column("raw_tdlib_json", sa.JSON(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("account_profile_audio_state")
