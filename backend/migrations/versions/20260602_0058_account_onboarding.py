"""Add account onboarding bounded context.

Revision ID: 20260602_0058
Revises: 20260526_0057
Create Date: 2026-06-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260602_0058"
down_revision = "20260526_0057"
branch_labels = None
depends_on = None

uuid_string = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")


def upgrade() -> None:
    op.create_table(
        "account_onboarding_batch",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("created_by_user_id", uuid_string, nullable=True),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("consent_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_actor_user_id", uuid_string, nullable=True),
        sa.Column("consent_version", sa.String(64), nullable=True),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ready_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocked_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requires_reauth_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(128), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["consent_actor_user_id"], ["app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_account_onboarding_batch_workspace_idempotency",
        ),
    )
    op.create_index(
        "ix_account_onboarding_batch_workspace_status",
        "account_onboarding_batch",
        ["workspace_id", "status"],
    )
    op.create_index(
        "ix_account_onboarding_batch_workspace_created",
        "account_onboarding_batch",
        ["workspace_id", "created_at"],
    )

    op.create_table(
        "account_onboarding_artifact",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("batch_id", uuid_string, nullable=True),
        sa.Column("item_id", uuid_string, nullable=True),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_type_detected", sa.String(255), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", uuid_string, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failure_code", sa.String(128), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["account_onboarding_batch.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_account_onboarding_artifact_workspace_status",
        "account_onboarding_artifact",
        ["workspace_id", "status"],
    )
    op.create_index(
        "ix_account_onboarding_artifact_expires", "account_onboarding_artifact", ["expires_at"]
    )

    op.create_table(
        "account_onboarding_item",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("batch_id", uuid_string, nullable=False),
        sa.Column("account_id", uuid_string, nullable=True),
        sa.Column("auth_session_id", uuid_string, nullable=True),
        sa.Column("artifact_id", uuid_string, nullable=True),
        sa.Column("source_ref_hash", sa.String(64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("phone_hint", sa.String(32), nullable=True),
        sa.Column("phone_normalized_hash", sa.String(64), nullable=True),
        sa.Column("username_hint", sa.String(255), nullable=True),
        sa.Column("telegram_user_id_hint", sa.String(255), nullable=True),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("validation_code", sa.String(128), nullable=True),
        sa.Column("validation_message", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.String(32), nullable=False),
        sa.Column("requires_reauth", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_error_code", sa.String(128), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["account_onboarding_batch.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.ForeignKeyConstraint(["auth_session_id"], ["telegram_auth_session.id"]),
        sa.ForeignKeyConstraint(["artifact_id"], ["account_onboarding_artifact.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id", "position", name="uq_account_onboarding_item_batch_position"
        ),
    )
    op.create_index(
        "ix_account_onboarding_item_workspace_batch",
        "account_onboarding_item",
        ["workspace_id", "batch_id"],
    )
    op.create_index(
        "ix_account_onboarding_item_batch_status", "account_onboarding_item", ["batch_id", "status"]
    )
    op.create_index(
        "ix_account_onboarding_item_workspace_phone_hash",
        "account_onboarding_item",
        ["workspace_id", "phone_normalized_hash"],
    )
    op.create_foreign_key(
        "fk_account_onboarding_artifact_item_id",
        "account_onboarding_artifact",
        "account_onboarding_item",
        ["item_id"],
        ["id"],
    )

    op.create_table(
        "account_onboarding_event",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("batch_id", uuid_string, nullable=False),
        sa.Column("item_id", uuid_string, nullable=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("actor_user_id", uuid_string, nullable=True),
        sa.Column("actor_type", sa.String(64), nullable=False),
        sa.Column("safe_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["account_onboarding_batch.id"]),
        sa.ForeignKeyConstraint(["item_id"], ["account_onboarding_item.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_account_onboarding_event_batch_created",
        "account_onboarding_event",
        ["batch_id", "created_at"],
    )
    op.create_index(
        "ix_account_onboarding_event_item_created",
        "account_onboarding_event",
        ["item_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_account_onboarding_event_item_created", table_name="account_onboarding_event")
    op.drop_index(
        "ix_account_onboarding_event_batch_created", table_name="account_onboarding_event"
    )
    op.drop_table("account_onboarding_event")
    op.drop_constraint(
        "fk_account_onboarding_artifact_item_id", "account_onboarding_artifact", type_="foreignkey"
    )
    op.drop_index(
        "ix_account_onboarding_item_workspace_phone_hash", table_name="account_onboarding_item"
    )
    op.drop_index("ix_account_onboarding_item_batch_status", table_name="account_onboarding_item")
    op.drop_index(
        "ix_account_onboarding_item_workspace_batch", table_name="account_onboarding_item"
    )
    op.drop_table("account_onboarding_item")
    op.drop_index(
        "ix_account_onboarding_artifact_expires", table_name="account_onboarding_artifact"
    )
    op.drop_index(
        "ix_account_onboarding_artifact_workspace_status", table_name="account_onboarding_artifact"
    )
    op.drop_table("account_onboarding_artifact")
    op.drop_index(
        "ix_account_onboarding_batch_workspace_created", table_name="account_onboarding_batch"
    )
    op.drop_index(
        "ix_account_onboarding_batch_workspace_status", table_name="account_onboarding_batch"
    )
    op.drop_table("account_onboarding_batch")
