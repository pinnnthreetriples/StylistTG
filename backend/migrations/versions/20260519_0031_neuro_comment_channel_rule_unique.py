"""Add unique channel rule constraint.

Revision ID: 20260519_0031
Revises: 20260519_0030
Create Date: 2026-05-19
"""

from __future__ import annotations

from alembic import op


revision = "20260519_0031"
down_revision = "20260519_0030"
branch_labels = None
depends_on = None


_CONSTRAINT_NAME = "uq_neuro_comment_channel_rule_workspace_ref_type"
_TABLE_NAME = "neuro_comment_channel_rules"


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM neuro_comment_channel_rules
        WHERE id IN (
            SELECT id
            FROM (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY workspace_id, target_ref, rule_type
                        ORDER BY created_at DESC, id DESC
                    ) AS duplicate_rank
                FROM neuro_comment_channel_rules
            ) ranked
            WHERE duplicate_rank > 1
        )
        """
    )
    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        batch_op.create_unique_constraint(
            _CONSTRAINT_NAME,
            ["workspace_id", "target_ref", "rule_type"],
        )


def downgrade() -> None:
    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        batch_op.drop_constraint(_CONSTRAINT_NAME, type_="unique")
