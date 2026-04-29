from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260424_0008"
down_revision: str | None = "20260424_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("job") as batch_op:
            batch_op.drop_constraint("uq_job_account_intent_state", type_="unique")
    else:
        op.drop_constraint("uq_job_account_intent_state", "job", type_="unique")
    op.create_index(
        "ix_job_active_intent_unique",
        "job",
        ["account_id", "execution_intent_hash"],
        unique=True,
        postgresql_where=sa.text("job_state IN ('queued', 'waiting_lock', 'running')"),
        sqlite_where=sa.text("job_state IN ('queued', 'waiting_lock', 'running')"),
    )
    op.create_index(
        "uq_account_story_post_job_step",
        "account_story_post",
        ["job_id", "step_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_account_story_post_job_step", table_name="account_story_post")
    op.drop_index("ix_job_active_intent_unique", table_name="job")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("job") as batch_op:
            batch_op.create_unique_constraint(
                "uq_job_account_intent_state",
                ["account_id", "execution_intent_hash", "job_state"],
            )
    else:
        op.create_unique_constraint(
            "uq_job_account_intent_state",
            "job",
            ["account_id", "execution_intent_hash", "job_state"],
        )
