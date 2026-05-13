from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.adapters.tdlib_profile_execution import build_profile_execution_adapter
from app.config import Settings, settings
from app.job_queue.workflows import enqueue_workflow
from app.models import Account, Job, JobState, utc_now
from app.modules.account_editing.executor import execute_account_update_job
from app.modules.account_editing.planner import (
    account_update_profile_payload,
    build_account_update_plan,
    compute_account_update_intent_hash,
    default_capability_snapshot,
)
from app.modules.account_editing.policies import AccountEditingPolicy
from app.modules.account_editing.repository import AccountEditingRepository
from app.services.execution_policy import ExecutionUsableAdapter
from app.services.step_registry import validate_account_update_plan_steps


ACCOUNT_UPDATE_WORKFLOW_TYPE = "account_update"


def build_preview(
    session: Session,
    *,
    account_id: str,
    desired_state: dict[str, Any],
    workspace_id: str,
    config: Settings = settings,
) -> dict[str, Any]:
    return build_account_update_preview(
        session,
        account_id=account_id,
        desired_state=desired_state,
        workspace_id=workspace_id,
        config=config,
    )


def create_job(
    session: Session,
    *,
    account_id: str,
    desired_state: dict[str, Any],
    requested_by_user_id: str | None,
    request_id: str | None,
    workspace_id: str,
    config: Settings = settings,
) -> Job:
    return create_account_update_job(
        session,
        account_id=account_id,
        desired_state=desired_state,
        execution_adapter=build_profile_execution_adapter(),
        config=config,
        requested_by_user_id=requested_by_user_id,
        request_id=request_id,
        workspace_id=workspace_id,
    )


def enqueue_job(job_id: str) -> bool:
    return enqueue_workflow(
        workflow_type=ACCOUNT_UPDATE_WORKFLOW_TYPE,
        job_id=job_id,
    )


def execute_inline_fallback(job_id: str, *, session: Session) -> None:
    execute_account_update_job(job_id, session=session)


def build_account_update_preview(
    session: Session,
    *,
    account_id: str,
    desired_state: dict[str, Any],
    workspace_id: str | None = None,
    config: Settings = settings,
) -> dict[str, Any]:
    repo = AccountEditingRepository(session)
    policy = AccountEditingPolicy(session)
    account = repo.require_account(account_id=account_id, workspace_id=workspace_id)

    requested_profile_fields = policy.requested_profile_fields(desired_state)
    desired_state = policy.normalize_desired_state_with_assets(
        account_id=account_id,
        desired_state=desired_state,
        workspace_id=account.workspace_id,
    )
    intent_hash = compute_account_update_intent_hash(account_id, desired_state)
    duplicate = repo.find_active_duplicate_job(account_id=account_id, intent_hash=intent_hash)
    plan = _build_plan_for_desired_state(
        policy=policy,
        account=account,
        desired_state=desired_state,
        requested_profile_fields=requested_profile_fields,
    )
    validate_account_update_plan_steps(plan)

    blocking_errors, warnings, safety_fields = policy.preview_safety(
        account=account,
        account_id=account_id,
        desired_state=desired_state,
        config=config,
    )

    return {
        "can_create_job": not blocking_errors,
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "normalized_payload": account_update_profile_payload(desired_state),
        "desired_state_normalized": desired_state,
        "execution_intent_hash": intent_hash,
        "workflow_type": "account_update",
        "workflow_version": 1,
        "capability_snapshot": default_capability_snapshot(),
        **safety_fields,
        "plan_json_snapshot": plan,
        "steps": plan["steps"],
        "requires_execution_usable": True,
        "dedup_would_block": duplicate is not None,
        "dedup_blocked_by_job_id": duplicate.id if duplicate else None,
    }


def create_account_update_job(
    session: Session,
    *,
    account_id: str,
    desired_state: dict[str, Any],
    execution_adapter: ExecutionUsableAdapter | None = None,
    config: Settings = settings,
    requested_by_user_id: str | None = None,
    created_from: str = "api",
    request_id: str | None = None,
    workspace_id: str | None = None,
) -> Job:
    repo = AccountEditingRepository(session)
    policy = AccountEditingPolicy(session)
    account = repo.validate_account_for_job(
        account_id=account_id,
        workspace_id=workspace_id,
        execution_adapter=execution_adapter,
    )
    requested_profile_fields = policy.requested_profile_fields(desired_state)
    desired_state = policy.normalize_desired_state_with_assets(
        account_id=account_id,
        desired_state=desired_state,
        workspace_id=account.workspace_id,
    )
    policy.validate_job_creation(
        account=account,
        account_id=account_id,
        desired_state=desired_state,
        config=config,
    )
    plan = _build_plan_for_desired_state(
        policy=policy,
        account=account,
        desired_state=desired_state,
        requested_profile_fields=requested_profile_fields,
    )
    validate_account_update_plan_steps(plan)
    intent_hash = compute_account_update_intent_hash(account_id, desired_state)
    duplicate = repo.find_active_duplicate_job(account_id=account_id, intent_hash=intent_hash)
    state = JobState.DEDUP_BLOCKED if duplicate else JobState.QUEUED
    job = Job(
        workspace_id=account.workspace_id,
        account_id=account_id,
        requested_by_user_id=requested_by_user_id,
        created_from=created_from,
        request_id=request_id,
        job_state=state,
        workflow_type="account_update",
        workflow_version=1,
        execution_intent_hash=intent_hash,
        job_payload_version=2,
        payload_json=account_update_profile_payload(desired_state),
        desired_state_json=desired_state,
        capability_snapshot_json=default_capability_snapshot(),
        plan_json_snapshot=plan,
        dedup_blocked_by_job_id=duplicate.id if duplicate else None,
        queued_at=utc_now() if not duplicate else None,
    )
    return repo.finalize_job_creation(
        job,
        requested_by_user_id=requested_by_user_id,
        request_id=request_id,
        log_event_name="account_update_job_created",
    )


create_job_legacy = create_account_update_job


def _build_plan_for_desired_state(
    *,
    policy: AccountEditingPolicy,
    account: Account,
    desired_state: dict[str, Any],
    requested_profile_fields: set[str],
) -> dict[str, Any]:
    return build_account_update_plan(
        desired_state,
        profile_step_types=policy.changed_profile_step_types(
            account=account,
            desired_state=desired_state,
            requested_profile_fields=requested_profile_fields,
        ),
    )
