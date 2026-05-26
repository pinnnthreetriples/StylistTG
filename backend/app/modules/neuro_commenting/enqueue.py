"""Canonical neuro-commenting enqueue facade."""

from __future__ import annotations

from uuid import uuid4

from app.job_queue import workflows


NEURO_GENERATE_COMMENT_WORKFLOW_TYPE = "neuro_generate_comment"
NEURO_OBSERVE_CAMPAIGN_WORKFLOW_TYPE = "neuro_observe_campaign"
NEURO_OBSERVE_TARGET_WORKFLOW_TYPE = "neuro_observe_target"
NEURO_REFRESH_TARGET_METADATA_WORKFLOW_TYPE = "neuro_refresh_target_metadata"
NEURO_SEND_ATTEMPT_WORKFLOW_TYPE = "neuro_send_attempt"


def enqueue_neuro_observe_campaign(
    campaign_id: str, workspace_id: str, *, limit: int | None, generate: bool
) -> bool:
    return workflows.enqueue_workflow(
        workflow_type=NEURO_OBSERVE_CAMPAIGN_WORKFLOW_TYPE,
        args=(campaign_id, workspace_id, limit, generate),
        job_id=f"neuro-observe-campaign-{campaign_id}",
    )


def enqueue_neuro_observe_target(
    campaign_id: str, target_id: str, workspace_id: str, *, limit: int | None, generate: bool
) -> bool:
    return workflows.enqueue_workflow(
        workflow_type=NEURO_OBSERVE_TARGET_WORKFLOW_TYPE,
        args=(campaign_id, target_id, workspace_id, limit, generate),
        job_id=f"neuro-observe-target-{target_id}",
    )


def enqueue_neuro_generate_comment(
    campaign_id: str,
    workspace_id: str,
    observed_post_id: str,
    *,
    force: bool = False,
    job_id: str | None = None,
) -> bool:
    resolved_job_id = job_id or neuro_generate_comment_job_id(observed_post_id, force=force)
    return workflows.enqueue_workflow(
        workflow_type=NEURO_GENERATE_COMMENT_WORKFLOW_TYPE,
        args=(campaign_id, workspace_id, observed_post_id, force),
        job_id=resolved_job_id,
        unique=not force,
    )


def enqueue_neuro_refresh_target_metadata(
    campaign_id: str, target_id: str, workspace_id: str
) -> bool:
    return workflows.enqueue_workflow(
        workflow_type=NEURO_REFRESH_TARGET_METADATA_WORKFLOW_TYPE,
        args=(campaign_id, target_id, workspace_id),
        job_id=f"neuro-refresh-target-{target_id}",
    )


def enqueue_neuro_send_attempt(attempt_id: str, workspace_id: str) -> bool:
    return workflows.enqueue_workflow(
        workflow_type=NEURO_SEND_ATTEMPT_WORKFLOW_TYPE,
        args=(attempt_id, workspace_id),
        job_id=f"neuro-send-{attempt_id}",
    )


def neuro_generate_comment_job_id(observed_post_id: str, *, force: bool = False) -> str:
    if force:
        return f"neuro-generate-force-{observed_post_id}-{uuid4()}"
    return f"neuro-generate-{observed_post_id}"


__all__ = [
    "NEURO_GENERATE_COMMENT_WORKFLOW_TYPE",
    "NEURO_OBSERVE_CAMPAIGN_WORKFLOW_TYPE",
    "NEURO_OBSERVE_TARGET_WORKFLOW_TYPE",
    "NEURO_REFRESH_TARGET_METADATA_WORKFLOW_TYPE",
    "NEURO_SEND_ATTEMPT_WORKFLOW_TYPE",
    "enqueue_neuro_generate_comment",
    "enqueue_neuro_observe_campaign",
    "enqueue_neuro_observe_target",
    "enqueue_neuro_refresh_target_metadata",
    "enqueue_neuro_send_attempt",
    "neuro_generate_comment_job_id",
]
