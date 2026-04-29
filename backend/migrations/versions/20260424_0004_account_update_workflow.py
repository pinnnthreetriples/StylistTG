from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260424_0004"
down_revision: str | None = "20260424_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("job", sa.Column("workflow_type", sa.String(length=64), nullable=False, server_default="profile_update"))
    op.add_column("job", sa.Column("workflow_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("job", sa.Column("desired_state_json", sa.JSON(), nullable=True))
    op.add_column("job", sa.Column("capability_snapshot_json", sa.JSON(), nullable=True))
    op.add_column("job", sa.Column("compensation_state", sa.String(length=64), nullable=True))
    op.add_column("job_step_result", sa.Column("step_order", sa.Integer(), nullable=True))
    op.add_column("job_step_result", sa.Column("capability_key", sa.String(length=128), nullable=True))
    op.add_column("job_step_result", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("job_step_result", sa.Column("compensation_status", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("job_step_result", "compensation_status")
    op.drop_column("job_step_result", "retry_count")
    op.drop_column("job_step_result", "capability_key")
    op.drop_column("job_step_result", "step_order")
    op.drop_column("job", "compensation_state")
    op.drop_column("job", "capability_snapshot_json")
    op.drop_column("job", "desired_state_json")
    op.drop_column("job", "workflow_version")
    op.drop_column("job", "workflow_type")
