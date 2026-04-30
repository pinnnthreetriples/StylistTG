"""store synced profile photo asset"""

from alembic import op
import sqlalchemy as sa

revision = "20260429_0012"
down_revision = "20260429_0011"
branch_labels = None
depends_on = None

UUID_STRING = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")


def upgrade() -> None:
    op.add_column("account_profile_state", sa.Column("profile_photo_asset_id", UUID_STRING, nullable=True))


def downgrade() -> None:
    op.drop_column("account_profile_state", "profile_photo_asset_id")
