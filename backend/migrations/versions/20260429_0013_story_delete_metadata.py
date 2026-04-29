"""store story deletion metadata"""

from alembic import op
import sqlalchemy as sa

revision = "20260429_0013"
down_revision = "20260429_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("account_story_post")}
    if "story_poster_chat_id" not in existing:
        op.add_column("account_story_post", sa.Column("story_poster_chat_id", sa.String(length=255), nullable=True))
    if "can_be_deleted" not in existing:
        op.add_column(
            "account_story_post",
            sa.Column("can_be_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("account_story_post")}
    if "can_be_deleted" in existing:
        op.drop_column("account_story_post", "can_be_deleted")
    if "story_poster_chat_id" in existing:
        op.drop_column("account_story_post", "story_poster_chat_id")
