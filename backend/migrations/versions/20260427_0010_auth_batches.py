"""auth batches

Revision ID: 20260427_0010
Revises: 20260424_0009
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260427_0010"
down_revision = "20260424_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_batch",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("cancelled_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("max_running_commands", sa.Integer(), nullable=False),
        sa.Column("max_waiting_input", sa.Integer(), nullable=False),
        sa.Column("max_total_active", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_auth_batch_idempotency_key"),
    )
    op.create_index("ix_auth_batch_status_created", "auth_batch", ["status", "created_at"])

    op.create_table(
        "auth_batch_item",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("phone_number", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("resend_count", sa.Integer(), nullable=False),
        sa.Column("code_error_count", sa.Integer(), nullable=False),
        sa.Column("password_error_count", sa.Integer(), nullable=False),
        sa.Column("locked_by", sa.String(length=255), nullable=True),
        sa.Column("lock_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["auth_batch.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "position", name="uq_auth_batch_item_batch_position"),
    )
    op.create_index("ix_auth_batch_item_batch_status", "auth_batch_item", ["batch_id", "status"])
    op.create_index("ix_auth_batch_item_lock_expires", "auth_batch_item", ["lock_expires_at"])
    op.create_index("ix_auth_batch_item_phone_status", "auth_batch_item", ["phone_number", "status"])

    op.create_table(
        "auth_attempt",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("batch_item_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["batch_item_id"], ["auth_batch_item.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_item_id", "attempt_number", "kind", name="uq_auth_attempt_item_number_kind"),
    )
    op.create_index("ix_auth_attempt_batch_item", "auth_attempt", ["batch_item_id"])

    op.create_table(
        "auth_batch_event",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("batch_item_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["auth_batch.id"]),
        sa.ForeignKeyConstraint(["batch_item_id"], ["auth_batch_item.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_batch_event_batch_created", "auth_batch_event", ["batch_id", "created_at"])
    op.create_index("ix_auth_batch_event_item_created", "auth_batch_event", ["batch_item_id", "created_at"])

    op.create_table(
        "idempotency_key",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index("ix_idempotency_key_expires", "idempotency_key", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_key_expires", table_name="idempotency_key")
    op.drop_table("idempotency_key")
    op.drop_index("ix_auth_batch_event_item_created", table_name="auth_batch_event")
    op.drop_index("ix_auth_batch_event_batch_created", table_name="auth_batch_event")
    op.drop_table("auth_batch_event")
    op.drop_index("ix_auth_attempt_batch_item", table_name="auth_attempt")
    op.drop_table("auth_attempt")
    op.drop_index("ix_auth_batch_item_phone_status", table_name="auth_batch_item")
    op.drop_index("ix_auth_batch_item_lock_expires", table_name="auth_batch_item")
    op.drop_index("ix_auth_batch_item_batch_status", table_name="auth_batch_item")
    op.drop_table("auth_batch_item")
    op.drop_index("ix_auth_batch_status_created", table_name="auth_batch")
    op.drop_table("auth_batch")
