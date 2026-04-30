"""add account operation cooldowns"""

from alembic import op
import sqlalchemy as sa

revision = "20260430_0015"
down_revision = "20260430_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()
    if "account_operation_cooldown" in tables:
        return
    op.create_table(
        "account_operation_cooldown",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("account.id"), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retry_after_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("source_job_id", sa.String(length=36), nullable=True),
        sa.Column("source_step_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_account_operation_cooldown_account_id", "account_operation_cooldown", ["account_id"])
    op.create_index("ix_account_operation_cooldown_operation", "account_operation_cooldown", ["operation"])


def downgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()
    if "account_operation_cooldown" not in tables:
        return
    op.drop_index("ix_account_operation_cooldown_operation", table_name="account_operation_cooldown")
    op.drop_index("ix_account_operation_cooldown_account_id", table_name="account_operation_cooldown")
    op.drop_table("account_operation_cooldown")
