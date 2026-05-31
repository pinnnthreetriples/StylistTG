"""account lifecycle and production execution plane foundation

Revision ID: 20260503_0021
Revises: 20260430_0020
Create Date: 2026-05-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260503_0021"
down_revision = "20260430_0020"
branch_labels = None
depends_on = None


uuid_string = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")


def upgrade() -> None:
    _create_sensitive_audit_event()
    _create_account_lifecycle_event()
    _create_account_deletion_request()
    _create_account_export_request()
    _create_job_execution_event()


def _create_sensitive_audit_event() -> None:
    op.create_table(
        "sensitive_audit_event",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("actor_user_id", uuid_string, nullable=True),
        sa.Column("actor_type", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("entity_id", uuid_string, nullable=True),
        sa.Column("account_id", uuid_string, nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("ip_hash", sa.String(length=128), nullable=True),
        sa.Column("user_agent_hash", sa.String(length=128), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.String(length=32), nullable=True),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sensitive_audit_event_workspace_id", "sensitive_audit_event", ["workspace_id"]
    )
    op.create_index("ix_sensitive_audit_event_account_id", "sensitive_audit_event", ["account_id"])
    op.create_index(
        "ix_sensitive_audit_workspace_created",
        "sensitive_audit_event",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_sensitive_audit_account_created", "sensitive_audit_event", ["account_id", "created_at"]
    )
    op.create_index(
        "ix_sensitive_audit_action_created", "sensitive_audit_event", ["action", "created_at"]
    )


def _create_account_lifecycle_event() -> None:
    op.create_table(
        "account_lifecycle_event",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("account_id", uuid_string, nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("actor_user_id", uuid_string, nullable=True),
        sa.Column("request_id", uuid_string, nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_account_lifecycle_event_workspace_id", "account_lifecycle_event", ["workspace_id"]
    )
    op.create_index(
        "ix_account_lifecycle_event_account_id", "account_lifecycle_event", ["account_id"]
    )
    op.create_index(
        "ix_account_lifecycle_workspace_created",
        "account_lifecycle_event",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_account_lifecycle_account_created",
        "account_lifecycle_event",
        ["account_id", "created_at"],
    )


def _create_account_deletion_request() -> None:
    op.create_table(
        "account_deletion_request",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("account_id", uuid_string, nullable=False),
        sa.Column("requested_by_user_id", uuid_string, nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("dry_run_result_json", sa.JSON(), nullable=True),
        sa.Column("execution_result_json", sa.JSON(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=128), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_account_deletion_request_workspace_id", "account_deletion_request", ["workspace_id"]
    )
    op.create_index(
        "ix_account_deletion_request_account_id", "account_deletion_request", ["account_id"]
    )
    op.create_index(
        "ix_account_deletion_workspace_status",
        "account_deletion_request",
        ["workspace_id", "status"],
    )
    op.create_index(
        "ix_account_deletion_account_status", "account_deletion_request", ["account_id", "status"]
    )


def _create_account_export_request() -> None:
    op.create_table(
        "account_export_request",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("account_id", uuid_string, nullable=False),
        sa.Column("requested_by_user_id", uuid_string, nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("export_key", sa.Text(), nullable=True),
        sa.Column("export_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("export_content_type", sa.String(length=128), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=128), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_account_export_request_workspace_id", "account_export_request", ["workspace_id"]
    )
    op.create_index(
        "ix_account_export_request_account_id", "account_export_request", ["account_id"]
    )
    op.create_index(
        "ix_account_export_workspace_status", "account_export_request", ["workspace_id", "status"]
    )
    op.create_index(
        "ix_account_export_account_created",
        "account_export_request",
        ["account_id", "requested_at"],
    )


def _create_job_execution_event() -> None:
    op.create_table(
        "job_execution_event",
        sa.Column("id", uuid_string, nullable=False),
        sa.Column("job_id", uuid_string, nullable=True),
        sa.Column("job_type", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", uuid_string, nullable=False),
        sa.Column("account_id", uuid_string, nullable=True),
        sa.Column("actor_user_id", uuid_string, nullable=True),
        sa.Column("queue_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("lock_key", sa.String(length=255), nullable=True),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("risk_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["job.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_execution_event_job_id", "job_execution_event", ["job_id"])
    op.create_index("ix_job_execution_event_workspace_id", "job_execution_event", ["workspace_id"])
    op.create_index("ix_job_execution_event_account_id", "job_execution_event", ["account_id"])
    op.create_index(
        "ix_job_execution_workspace_created", "job_execution_event", ["workspace_id", "created_at"]
    )
    op.create_index(
        "ix_job_execution_account_created", "job_execution_event", ["account_id", "created_at"]
    )
    op.create_index("ix_job_execution_job_created", "job_execution_event", ["job_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_job_execution_job_created", table_name="job_execution_event")
    op.drop_index("ix_job_execution_account_created", table_name="job_execution_event")
    op.drop_index("ix_job_execution_workspace_created", table_name="job_execution_event")
    op.drop_index("ix_job_execution_event_account_id", table_name="job_execution_event")
    op.drop_index("ix_job_execution_event_workspace_id", table_name="job_execution_event")
    op.drop_index("ix_job_execution_event_job_id", table_name="job_execution_event")
    op.drop_table("job_execution_event")
    op.drop_index("ix_account_export_account_created", table_name="account_export_request")
    op.drop_index("ix_account_export_workspace_status", table_name="account_export_request")
    op.drop_index("ix_account_export_request_account_id", table_name="account_export_request")
    op.drop_index("ix_account_export_request_workspace_id", table_name="account_export_request")
    op.drop_table("account_export_request")
    op.drop_index("ix_account_deletion_account_status", table_name="account_deletion_request")
    op.drop_index("ix_account_deletion_workspace_status", table_name="account_deletion_request")
    op.drop_index("ix_account_deletion_request_account_id", table_name="account_deletion_request")
    op.drop_index("ix_account_deletion_request_workspace_id", table_name="account_deletion_request")
    op.drop_table("account_deletion_request")
    op.drop_index("ix_account_lifecycle_account_created", table_name="account_lifecycle_event")
    op.drop_index("ix_account_lifecycle_workspace_created", table_name="account_lifecycle_event")
    op.drop_index("ix_account_lifecycle_event_account_id", table_name="account_lifecycle_event")
    op.drop_index("ix_account_lifecycle_event_workspace_id", table_name="account_lifecycle_event")
    op.drop_table("account_lifecycle_event")
    op.drop_index("ix_sensitive_audit_action_created", table_name="sensitive_audit_event")
    op.drop_index("ix_sensitive_audit_account_created", table_name="sensitive_audit_event")
    op.drop_index("ix_sensitive_audit_workspace_created", table_name="sensitive_audit_event")
    op.drop_index("ix_sensitive_audit_event_account_id", table_name="sensitive_audit_event")
    op.drop_index("ix_sensitive_audit_event_workspace_id", table_name="sensitive_audit_event")
    op.drop_table("sensitive_audit_event")
