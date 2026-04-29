from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260429_0011"
down_revision: str | None = "20260427_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("asset", sa.Column("original_filename", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("asset", "original_filename")
