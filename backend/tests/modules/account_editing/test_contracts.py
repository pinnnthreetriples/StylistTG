from __future__ import annotations

from app.config import Settings
from app.models import JobState
from app.modules.account_editing import service
from app.modules.account_editing.planner import JOB_PAYLOAD_VERSION, WORKFLOW_VERSION
from app.modules.registry import get_workflow_spec
from tests.helpers.factories import seed_account_with_profile


def test_workflow_contract_identifiers_remain_stable() -> None:
    workflow = get_workflow_spec("account_update")

    assert workflow.workflow_type == "account_update"
    assert WORKFLOW_VERSION == 1
    assert JOB_PAYLOAD_VERSION == 2


def test_preview_response_keeps_expected_contract_keys(db_session) -> None:
    account = seed_account_with_profile(db_session)

    preview = service.build_account_update_preview(
        db_session,
        account_id=account.id,
        desired_state={"profile": {"name": "Stylist TG"}},
        workspace_id=account.workspace_id,
        config=Settings(profile_job_cooldown_seconds=0),
    )

    assert {
        "can_create_job",
        "blocking_errors",
        "warnings",
        "normalized_payload",
        "desired_state_normalized",
        "execution_intent_hash",
        "plan_json_snapshot",
        "steps",
        "requires_execution_usable",
        "dedup_would_block",
    }.issubset(preview)


def test_create_job_queues_without_duplicate_and_dedup_blocks_duplicate(db_session) -> None:
    account = seed_account_with_profile(db_session)
    desired_state = {"profile": {"name": "Stylist TG"}}

    first = service.create_account_update_job(
        db_session,
        account_id=account.id,
        desired_state=desired_state,
        config=Settings(profile_job_cooldown_seconds=0),
        workspace_id=account.workspace_id,
    )
    second = service.create_account_update_job(
        db_session,
        account_id=account.id,
        desired_state=desired_state,
        config=Settings(profile_job_cooldown_seconds=0),
        workspace_id=account.workspace_id,
    )

    assert first.job_state == JobState.QUEUED
    assert second.job_state == JobState.DEDUP_BLOCKED
    assert second.dedup_blocked_by_job_id == first.id
