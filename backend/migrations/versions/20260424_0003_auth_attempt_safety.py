from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260424_0003"
down_revision: str | None = "20260423_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_STRING = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")


def upgrade() -> None:
    op.create_table(
        "account_auth_attempt",
        sa.Column("id", UUID_STRING, primary_key=True),
        sa.Column("account_id", UUID_STRING, sa.ForeignKey("account.id"), nullable=False),
        sa.Column("external_ref", sa.String(length=255), nullable=False),
        sa.Column("attempt_kind", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=128), nullable=False),
        sa.Column("blocked_reason", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("account_auth_attempt")
