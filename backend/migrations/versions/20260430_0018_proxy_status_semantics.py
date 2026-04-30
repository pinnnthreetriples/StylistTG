"""Add detailed proxy verification fields."""

from alembic import op
import sqlalchemy as sa


revision = "20260430_0018"
down_revision = "20260430_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("account_proxy", sa.Column("last_check_scope", sa.String(length=32), nullable=True))
    op.add_column("account_proxy", sa.Column("tdlib_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("account_proxy", sa.Column("tdlib_last_error_code", sa.String(length=128), nullable=True))
    op.add_column("account_proxy", sa.Column("tdlib_last_error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("account_proxy", "tdlib_last_error_message")
    op.drop_column("account_proxy", "tdlib_last_error_code")
    op.drop_column("account_proxy", "tdlib_verified_at")
    op.drop_column("account_proxy", "last_check_scope")
