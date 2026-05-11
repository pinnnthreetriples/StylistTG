"""add account safety snapshots and validity check runs"""

from alembic import op
import sqlalchemy as sa

revision = "20260430_0014"
down_revision = "20260429_0013"
branch_labels = None
depends_on = None

UUID_STRING = sa.String(length=36).with_variant(sa.Uuid(as_uuid=False), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if "account_safety_snapshot" not in tables:
        op.create_table(
            "account_safety_snapshot",
            sa.Column("account_id", UUID_STRING, sa.ForeignKey("account.id"), primary_key=True),
            sa.Column("health_status", sa.String(length=64), nullable=False),
            sa.Column("overall_risk_level", sa.String(length=64), nullable=False),
            sa.Column("validity_status", sa.String(length=64), nullable=False),
            sa.Column("capabilities_json", sa.JSON(), nullable=False),
            sa.Column("risk_by_operation_json", sa.JSON(), nullable=False),
            sa.Column("reasons_json", sa.JSON(), nullable=False),
            sa.Column("signals_json", sa.JSON(), nullable=False),
            sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("source", sa.String(length=64), nullable=False, server_default="db_snapshot"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "account_validity_check_run" not in tables:
        op.create_table(
            "account_validity_check_run",
            sa.Column("id", UUID_STRING, primary_key=True),
            sa.Column("account_id", UUID_STRING, sa.ForeignKey("account.id"), nullable=False),
            sa.Column("mode", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=64), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_code", sa.String(length=128), nullable=True),
            sa.Column("error_class", sa.String(length=255), nullable=True),
            sa.Column("details_json", sa.JSON(), nullable=True),
            sa.Column("result_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_account_validity_check_run_account_id", "account_validity_check_run", ["account_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if "account_validity_check_run" in tables:
        op.drop_index(
            "ix_account_validity_check_run_account_id", table_name="account_validity_check_run"
        )
        op.drop_table("account_validity_check_run")
    if "account_safety_snapshot" in tables:
        op.drop_table("account_safety_snapshot")
