"""hot-path indexes for performance

Revision ID: 20260510_0027
Revises: 20260509_0026
Create Date: 2026-05-10
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260510_0027"
down_revision: str | None = "20260509_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _create_account_and_job_indexes()
    _create_safety_indexes()
    _create_story_indexes()


def _create_account_and_job_indexes() -> None:
    op.create_index("ix_account_workspace_updated", "account", ["workspace_id", "updated_at"])
    op.create_index("ix_job_account_queued", "job", ["account_id", "queued_at"])
    op.create_index(
        "ix_job_workspace_account_queued",
        "job",
        ["workspace_id", "account_id", "queued_at"],
    )
    op.create_index(
        "ix_job_account_intent_state",
        "job",
        ["account_id", "execution_intent_hash", "job_state"],
    )
    op.create_index("ix_job_account_finished", "job", ["account_id", "finished_at"])
    op.create_index(
        "ix_job_step_result_job_started",
        "job_step_result",
        ["job_id", "started_at"],
    )
    op.create_index(
        "ix_job_step_result_job_status_finished",
        "job_step_result",
        ["job_id", "status", "finished_at"],
    )


def _create_safety_indexes() -> None:
    op.create_index(
        "ix_validity_check_account_started",
        "account_validity_check_run",
        ["account_id", "started_at"],
    )
    op.create_index(
        "ix_cooldown_account_op_retry",
        "account_operation_cooldown",
        ["account_id", "operation", "retry_after_at"],
    )
    op.create_index(
        "ix_override_account_op_until",
        "account_safety_override",
        ["account_id", "operation", "allowed_until"],
    )
    op.create_index(
        "ix_operation_log_workspace_created",
        "account_operation_log",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_operation_log_ws_type_status_created",
        "account_operation_log",
        ["workspace_id", "operation_type", "status", "created_at"],
    )


def _create_story_indexes() -> None:
    op.create_index(
        "ix_story_draft_account_updated",
        "account_story_draft",
        ["account_id", "updated_at"],
    )
    op.create_index(
        "ix_story_draft_account_asset",
        "account_story_draft",
        ["account_id", "asset_id"],
    )
    op.create_index(
        "ix_story_post_account_status_created",
        "account_story_post",
        ["account_id", "status", "created_at"],
    )
    op.create_index(
        "ix_story_post_account_asset",
        "account_story_post",
        ["account_id", "asset_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_story_post_account_asset", table_name="account_story_post")
    op.drop_index("ix_story_post_account_status_created", table_name="account_story_post")
    op.drop_index("ix_story_draft_account_asset", table_name="account_story_draft")
    op.drop_index("ix_story_draft_account_updated", table_name="account_story_draft")
    op.drop_index("ix_operation_log_ws_type_status_created", table_name="account_operation_log")
    op.drop_index("ix_operation_log_workspace_created", table_name="account_operation_log")
    op.drop_index("ix_override_account_op_until", table_name="account_safety_override")
    op.drop_index("ix_cooldown_account_op_retry", table_name="account_operation_cooldown")
    op.drop_index("ix_validity_check_account_started", table_name="account_validity_check_run")
    op.drop_index("ix_job_step_result_job_status_finished", table_name="job_step_result")
    op.drop_index("ix_job_step_result_job_started", table_name="job_step_result")
    op.drop_index("ix_job_account_finished", table_name="job")
    op.drop_index("ix_job_account_intent_state", table_name="job")
    op.drop_index("ix_job_workspace_account_queued", table_name="job")
    op.drop_index("ix_job_account_queued", table_name="job")
    op.drop_index("ix_account_workspace_updated", table_name="account")
