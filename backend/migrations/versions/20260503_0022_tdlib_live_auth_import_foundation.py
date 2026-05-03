"""tdlib live auth and import foundation

Revision ID: 20260503_0022
Revises: 20260503_0021
Create Date: 2026-05-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260503_0022"
down_revision = "20260503_0021"
branch_labels = None
depends_on = None


uuid_string = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")


def upgrade() -> None:
    op.create_table(
        "telegram_auth_session",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("account_id", uuid_string, nullable=True),
        sa.Column("phone_hint", sa.String(length=64), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("tdlib_storage_key", sa.String(length=255), nullable=True),
        sa.Column("requires_code", sa.Boolean(), nullable=False),
        sa.Column("requires_password", sa.Boolean(), nullable=False),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", uuid_string, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_telegram_auth_session_workspace_id", "telegram_auth_session", ["workspace_id"])
    op.create_index("ix_telegram_auth_session_account_id", "telegram_auth_session", ["account_id"])
    op.create_index("ix_telegram_auth_session_workspace_status", "telegram_auth_session", ["workspace_id", "status"])
    op.create_index("ix_telegram_auth_session_account_created", "telegram_auth_session", ["account_id", "created_at"])

    op.create_table(
        "account_import_batch",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("created_by_user_id", uuid_string, nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=128), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_import_batch_workspace_id", "account_import_batch", ["workspace_id"])
    op.create_index("ix_account_import_batch_workspace_status", "account_import_batch", ["workspace_id", "status"])
    op.create_index("ix_account_import_batch_created", "account_import_batch", ["workspace_id", "created_at"])

    op.create_table(
        "account_import_item",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("batch_id", uuid_string, nullable=False),
        sa.Column("account_id", uuid_string, nullable=True),
        sa.Column("source_ref_hash", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("phone_hint", sa.String(length=64), nullable=True),
        sa.Column("username_hint", sa.String(length=255), nullable=True),
        sa.Column("validation_code", sa.String(length=128), nullable=True),
        sa.Column("validation_message", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["account_import_batch.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_import_item_workspace_id", "account_import_item", ["workspace_id"])
    op.create_index("ix_account_import_item_batch_id", "account_import_item", ["batch_id"])
    op.create_index("ix_account_import_item_batch_status", "account_import_item", ["batch_id", "status"])
    op.create_index("ix_account_import_item_workspace_status", "account_import_item", ["workspace_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_account_import_item_workspace_status", table_name="account_import_item")
    op.drop_index("ix_account_import_item_batch_status", table_name="account_import_item")
    op.drop_index("ix_account_import_item_batch_id", table_name="account_import_item")
    op.drop_index("ix_account_import_item_workspace_id", table_name="account_import_item")
    op.drop_table("account_import_item")
    op.drop_index("ix_account_import_batch_created", table_name="account_import_batch")
    op.drop_index("ix_account_import_batch_workspace_status", table_name="account_import_batch")
    op.drop_index("ix_account_import_batch_workspace_id", table_name="account_import_batch")
    op.drop_table("account_import_batch")
    op.drop_index("ix_telegram_auth_session_account_created", table_name="telegram_auth_session")
    op.drop_index("ix_telegram_auth_session_workspace_status", table_name="telegram_auth_session")
    op.drop_index("ix_telegram_auth_session_account_id", table_name="telegram_auth_session")
    op.drop_index("ix_telegram_auth_session_workspace_id", table_name="telegram_auth_session")
    op.drop_table("telegram_auth_session")
