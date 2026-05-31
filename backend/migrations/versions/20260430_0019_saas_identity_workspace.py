"""Add SaaS identity, workspace ownership, audit and limits foundation."""

from alembic import op
import sqlalchemy as sa
from datetime import UTC, datetime


revision = "20260430_0019"
down_revision = "20260430_0018"
branch_labels = None
depends_on = None

UUID_STRING = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")
DEFAULT_USER_ID = "00000000-0000-4000-8000-000000000001"
DEFAULT_WORKSPACE_ID = "00000000-0000-4000-8000-000000000002"


def upgrade() -> None:
    _create_owner_tables()
    _create_workspace_limit_tables()
    _seed_default_user_and_workspace()
    _seed_default_membership_and_plan()
    _attach_workspace_columns()
    _extend_job_identity()


def _create_owner_tables() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", UUID_STRING, primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("external_auth_provider", sa.String(length=64), nullable=False),
        sa.Column("external_auth_user_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "external_auth_provider", "external_auth_user_id", name="uq_user_external_auth"
        ),
    )
    op.create_index("ix_user_email", "app_user", ["email"])

    op.create_table(
        "workspace",
        sa.Column("id", UUID_STRING, primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("owner_user_id", UUID_STRING, sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_workspace_slug"),
    )

    op.create_table(
        "workspace_member",
        sa.Column("id", UUID_STRING, primary_key=True),
        sa.Column("workspace_id", UUID_STRING, sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("user_id", UUID_STRING, sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member_workspace_user"),
    )
    op.create_index("ix_workspace_member_workspace_id", "workspace_member", ["workspace_id"])
    op.create_index("ix_workspace_member_user_id", "workspace_member", ["user_id"])


def _create_workspace_limit_tables() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", UUID_STRING, primary_key=True),
        sa.Column("workspace_id", UUID_STRING, sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("actor_user_id", UUID_STRING, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("entity_id", UUID_STRING, nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_log_workspace_created", "audit_log", ["workspace_id", "created_at"])
    op.create_index("ix_audit_log_workspace_id", "audit_log", ["workspace_id"])

    op.create_table(
        "workspace_plan",
        sa.Column("workspace_id", UUID_STRING, sa.ForeignKey("workspace.id"), primary_key=True),
        sa.Column("plan_code", sa.String(length=64), nullable=False),
        sa.Column("billing_status", sa.String(length=64), nullable=False),
        sa.Column("max_accounts", sa.Integer(), nullable=False),
        sa.Column("max_jobs_per_day", sa.Integer(), nullable=False),
        sa.Column("max_batch_size", sa.Integer(), nullable=False),
        sa.Column("max_storage_mb", sa.Integer(), nullable=False),
        sa.Column("max_team_members", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "usage_counter",
        sa.Column("id", UUID_STRING, primary_key=True),
        sa.Column("workspace_id", UUID_STRING, sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "workspace_id",
            "period_start",
            "period_end",
            "metric",
            name="uq_usage_counter_period_metric",
        ),
    )
    op.create_index("ix_usage_counter_workspace_id", "usage_counter", ["workspace_id"])


def _seed_default_user_and_workspace() -> None:
    now = datetime.now(UTC)
    op.bulk_insert(
        sa.table(
            "app_user",
            sa.column("id", UUID_STRING),
            sa.column("email", sa.String),
            sa.column("display_name", sa.String),
            sa.column("external_auth_provider", sa.String),
            sa.column("external_auth_user_id", sa.String),
            sa.column("status", sa.String),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {
                "id": DEFAULT_USER_ID,
                "email": "local@stylisttg.local",
                "display_name": "Local Operator",
                "external_auth_provider": "local",
                "external_auth_user_id": "local-operator",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    op.bulk_insert(
        sa.table(
            "workspace",
            sa.column("id", UUID_STRING),
            sa.column("name", sa.String),
            sa.column("slug", sa.String),
            sa.column("owner_user_id", UUID_STRING),
            sa.column("status", sa.String),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {
                "id": DEFAULT_WORKSPACE_ID,
                "name": "Local Workspace",
                "slug": "local",
                "owner_user_id": DEFAULT_USER_ID,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def _seed_default_membership_and_plan() -> None:
    now = datetime.now(UTC)
    op.bulk_insert(
        sa.table(
            "workspace_member",
            sa.column("id", UUID_STRING),
            sa.column("workspace_id", UUID_STRING),
            sa.column("user_id", UUID_STRING),
            sa.column("role", sa.String),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {
                "id": "00000000-0000-4000-8000-000000000003",
                "workspace_id": DEFAULT_WORKSPACE_ID,
                "user_id": DEFAULT_USER_ID,
                "role": "owner",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    op.bulk_insert(
        sa.table(
            "workspace_plan",
            sa.column("workspace_id", UUID_STRING),
            sa.column("plan_code", sa.String),
            sa.column("billing_status", sa.String),
            sa.column("max_accounts", sa.Integer),
            sa.column("max_jobs_per_day", sa.Integer),
            sa.column("max_batch_size", sa.Integer),
            sa.column("max_storage_mb", sa.Integer),
            sa.column("max_team_members", sa.Integer),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {
                "workspace_id": DEFAULT_WORKSPACE_ID,
                "plan_code": "local",
                "billing_status": "active",
                "max_accounts": 1000,
                "max_jobs_per_day": 10000,
                "max_batch_size": 1000,
                "max_storage_mb": 10240,
                "max_team_members": 10,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def _attach_workspace_columns() -> None:
    for table_name in ("account", "auth_batch", "job", "asset", "account_operation_log"):
        op.add_column(
            table_name,
            sa.Column(
                "workspace_id",
                UUID_STRING,
                sa.ForeignKey("workspace.id"),
                nullable=False,
                server_default=DEFAULT_WORKSPACE_ID,
            ),
        )
        op.create_index(f"ix_{table_name}_workspace_id", table_name, ["workspace_id"])


def _extend_job_identity() -> None:
    op.add_column(
        "job",
        sa.Column("requested_by_user_id", UUID_STRING, sa.ForeignKey("app_user.id"), nullable=True),
    )
    op.add_column(
        "job",
        sa.Column("approved_by_user_id", UUID_STRING, sa.ForeignKey("app_user.id"), nullable=True),
    )
    op.add_column(
        "job", sa.Column("created_from", sa.String(length=64), nullable=False, server_default="api")
    )
    op.add_column("job", sa.Column("request_id", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("job", "request_id")
    op.drop_column("job", "created_from")
    op.drop_column("job", "approved_by_user_id")
    op.drop_column("job", "requested_by_user_id")
    for table_name in ("account_operation_log", "asset", "job", "auth_batch", "account"):
        op.drop_index(f"ix_{table_name}_workspace_id", table_name=table_name)
        op.drop_column(table_name, "workspace_id")
    op.drop_index("ix_usage_counter_workspace_id", table_name="usage_counter")
    op.drop_table("usage_counter")
    op.drop_table("workspace_plan")
    op.drop_index("ix_audit_log_workspace_id", table_name="audit_log")
    op.drop_index("ix_audit_log_workspace_created", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_workspace_member_user_id", table_name="workspace_member")
    op.drop_index("ix_workspace_member_workspace_id", table_name="workspace_member")
    op.drop_table("workspace_member")
    op.drop_table("workspace")
    op.drop_index("ix_user_email", table_name="app_user")
    op.drop_table("app_user")
