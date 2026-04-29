from collections.abc import Sequence

from alembic import op

revision: str = "20260424_0009"
down_revision: str | None = "20260424_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_auth_attempt_account_kind_created",
        "account_auth_attempt",
        ["account_id", "attempt_kind", "created_at"],
    )
    op.create_index(
        "ix_auth_attempt_ref_kind_created",
        "account_auth_attempt",
        ["external_ref", "attempt_kind", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_auth_attempt_ref_kind_created", table_name="account_auth_attempt")
    op.drop_index("ix_auth_attempt_account_kind_created", table_name="account_auth_attempt")
