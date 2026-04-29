from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260423_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_STRING = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")


def upgrade() -> None:
    op.create_table(
        "account",
        sa.Column("id", UUID_STRING, primary_key=True),
        sa.Column("external_ref", sa.String(length=255), nullable=False, unique=True),
        sa.Column("telegram_user_id", sa.String(length=255), nullable=True),
        sa.Column("auth_source", sa.String(length=64), nullable=False),
        sa.Column("account_state", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "asset",
        sa.Column("id", UUID_STRING, primary_key=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("normalized_path", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("mime", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_asset_content_hash", "asset", ["content_hash"])
    op.create_table(
        "account_runtime_state",
        sa.Column("account_id", UUID_STRING, sa.ForeignKey("account.id"), primary_key=True),
        sa.Column("session_present", sa.Boolean(), nullable=False),
        sa.Column("authorized_last_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("runtime_health", sa.String(length=64), nullable=False),
        sa.Column("reauth_required", sa.Boolean(), nullable=False),
        sa.Column("lock_owner", sa.String(length=255), nullable=True),
        sa.Column("lock_epoch", sa.Integer(), nullable=False),
        sa.Column("recovery_marker", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "job",
        sa.Column("id", UUID_STRING, primary_key=True),
        sa.Column("account_id", UUID_STRING, sa.ForeignKey("account.id"), nullable=False),
        sa.Column("job_state", sa.String(length=64), nullable=False),
        sa.Column("execution_intent_hash", sa.String(length=64), nullable=False),
        sa.Column("job_payload_version", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("plan_json_snapshot", sa.JSON(), nullable=False),
        sa.Column("dedup_blocked_by_job_id", UUID_STRING, nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "account_id",
            "execution_intent_hash",
            "job_state",
            name="uq_job_account_intent_state",
        ),
    )
    op.create_table(
        "job_step_result",
        sa.Column("id", UUID_STRING, primary_key=True),
        sa.Column("job_id", UUID_STRING, sa.ForeignKey("job.id"), nullable=False),
        sa.Column("step_key", sa.String(length=128), nullable=False),
        sa.Column("step_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("uncertain_reason", sa.Text(), nullable=True),
        sa.Column("verification_attempted", sa.Boolean(), nullable=False),
        sa.Column("verification_result", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_class", sa.String(length=255), nullable=True),
        sa.Column("result_payload_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("job_step_result")
    op.drop_table("job")
    op.drop_table("account_runtime_state")
    op.drop_index("ix_asset_content_hash", table_name="asset")
    op.drop_table("asset")
    op.drop_table("account")
