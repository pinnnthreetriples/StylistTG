"""Add account operation logs and account proxy."""

from alembic import op
import sqlalchemy as sa


revision = "20260430_0017"
down_revision = "20260430_0016"
branch_labels = None
depends_on = None

UUID_STRING = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")


def upgrade() -> None:
    op.create_table(
        "account_operation_log",
        sa.Column("id", UUID_STRING, primary_key=True),
        sa.Column("account_id", UUID_STRING, sa.ForeignKey("account.id"), nullable=False),
        sa.Column("operation_type", sa.String(length=64), nullable=False),
        sa.Column("operation_key", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_class", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("job_id", UUID_STRING, nullable=True),
        sa.Column("step_id", UUID_STRING, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_account_operation_log_account_id", "account_operation_log", ["account_id"])
    op.create_index(
        "ix_operation_log_account_created",
        "account_operation_log",
        ["account_id", "created_at"],
    )
    op.create_index(
        "ix_operation_log_type_status_created",
        "account_operation_log",
        ["operation_type", "status", "created_at"],
    )

    op.create_table(
        "account_proxy",
        sa.Column("account_id", UUID_STRING, sa.ForeignKey("account.id"), primary_key=True),
        sa.Column("proxy_type", sa.String(length=16), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("password_encrypted", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("account_proxy")
    op.drop_index("ix_operation_log_type_status_created", table_name="account_operation_log")
    op.drop_index("ix_operation_log_account_created", table_name="account_operation_log")
    op.drop_index("ix_account_operation_log_account_id", table_name="account_operation_log")
    op.drop_table("account_operation_log")
