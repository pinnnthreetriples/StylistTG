"""workspace-scoped idempotency keys

Revision ID: 20260509_0026
Revises: 20260508_0025
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20260509_0026"
down_revision = "20260508_0025"
branch_labels = None
depends_on = None

UUID_STRING = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")

DEFAULT_LOCAL_WORKSPACE_ID = "00000000-0000-4000-8000-000000000001"


def upgrade() -> None:
    # --- auth_batch: global unique → workspace-scoped unique ---
    op.drop_constraint("uq_auth_batch_idempotency_key", "auth_batch", type_="unique")
    op.create_unique_constraint(
        "uq_auth_batch_workspace_idempotency_key",
        "auth_batch",
        ["workspace_id", "idempotency_key"],
    )

    # --- idempotency_key: add workspace_id to composite PK ---
    # Keys are ephemeral (10-min TTL); drop and recreate is safe.
    op.drop_index("ix_idempotency_key_expires", table_name="idempotency_key")
    op.drop_table("idempotency_key")
    op.create_table(
        "idempotency_key",
        sa.Column("workspace_id", UUID_STRING, nullable=False, server_default=DEFAULT_LOCAL_WORKSPACE_ID),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=128), nullable=False),
        sa.Column("entity_id", UUID_STRING, nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], name="fk_idempotency_key_workspace"),
        sa.PrimaryKeyConstraint("workspace_id", "key", name="pk_idempotency_key"),
    )
    op.create_index("ix_idempotency_key_expires", "idempotency_key", ["expires_at"])


def downgrade() -> None:
    # --- idempotency_key: restore single-column PK ---
    op.drop_index("ix_idempotency_key_expires", table_name="idempotency_key")
    op.drop_table("idempotency_key")
    op.create_table(
        "idempotency_key",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=128), nullable=False),
        sa.Column("entity_id", UUID_STRING, nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index("ix_idempotency_key_expires", "idempotency_key", ["expires_at"])

    # --- auth_batch: restore global unique ---
    op.drop_constraint("uq_auth_batch_workspace_idempotency_key", "auth_batch", type_="unique")
    op.create_unique_constraint(
        "uq_auth_batch_idempotency_key",
        "auth_batch",
        ["idempotency_key"],
    )
