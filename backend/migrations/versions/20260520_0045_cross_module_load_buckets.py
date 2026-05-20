"""Create cross_module_load_buckets table.

Task 17: CrossModuleLoadTracker rolling hourly counters across warmup,
commenting, editing, and other modules.

Revision ID: 20260520_0045
Revises: 20260520_0044
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260520_0045"
down_revision = "20260520_0044"
branch_labels = None
depends_on = None

UUID_STRING = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")


def upgrade() -> None:
    op.create_table(
        "cross_module_load_buckets",
        sa.Column("id", UUID_STRING, nullable=False),
        sa.Column("workspace_id", UUID_STRING, nullable=False),
        sa.Column("account_id", UUID_STRING, nullable=False),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("warmup_actions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("commenting_actions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("editing_actions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("other_actions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "total_actions",
            sa.Integer(),
            sa.Computed(
                "warmup_actions + commenting_actions + editing_actions + other_actions",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "account_id",
            "bucket_start",
            name="uq_cross_module_load_buckets_ws_account_bucket",
        ),
    )
    op.create_index(
        "ix_cross_module_load_buckets_workspace_id",
        "cross_module_load_buckets",
        ["workspace_id"],
    )
    op.create_index(
        "ix_cross_module_load_buckets_account_id",
        "cross_module_load_buckets",
        ["account_id"],
    )
    op.create_index(
        "ix_cross_module_load_buckets_bucket_start",
        "cross_module_load_buckets",
        ["bucket_start"],
    )
    op.create_index(
        "ix_cross_module_load_buckets_account_bucket_start",
        "cross_module_load_buckets",
        ["account_id", "bucket_start"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cross_module_load_buckets_account_bucket_start",
        table_name="cross_module_load_buckets",
    )
    op.drop_index(
        "ix_cross_module_load_buckets_bucket_start",
        table_name="cross_module_load_buckets",
    )
    op.drop_index(
        "ix_cross_module_load_buckets_account_id",
        table_name="cross_module_load_buckets",
    )
    op.drop_index(
        "ix_cross_module_load_buckets_workspace_id",
        table_name="cross_module_load_buckets",
    )
    op.drop_table("cross_module_load_buckets")
