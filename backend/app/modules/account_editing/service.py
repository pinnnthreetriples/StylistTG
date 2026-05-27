from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.adapters.tdlib_profile_execution import build_profile_execution_adapter
from app.config import Settings, settings
from app.logging_utils import log_event
from app.models import Account, Job, JobState, utc_now
from app.modules.account_editing.contracts import (
    AccountUpdateCreate,
    AccountUpdateJobSummaryRead,
    AccountUpdatePreviewRead,
)
from app.modules.account_editing.enqueue import enqueue_account_update_job
from app.modules.account_editing.executor import execute_account_update_job
from app.modules.account_editing.errors import (
    AccountQueueUnavailableError,
    AccountWarmupLockedError,
)
from app.modules.account_editing.planner import (
    account_update_profile_payload,
    build_account_update_plan,
    compute_account_update_intent_hash,
    default_capability_snapshot,
)
from app.modules.account_editing.policies import AccountEditingPolicy
from app.modules.account_editing.repository import AccountEditingRepository
from app.modules.account_safety.service import evaluate as evaluate_safety_gate
from app.modules.warmup import service as warmup_service
from app.services.dashboard import job_summary
from app.services.execution_policy import ExecutionUsableAdapter
from app.services.operation_logs import log_operation
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


def build_preview_use_case(
    session: Session,
    *,
    payload: AccountUpdateCreate,
    workspace_id: str,
    config: Settings = settings,
) -> AccountUpdatePreviewRead:
    preview = build_preview(
        session,
        account_id=payload.account_id,
        desired_state=payload.model_dump(exclude={"account_id"}, exclude_none=True),
        workspace_id=workspace_id,
        config=config,
    )
    log_operation(
        session,
        account_id=payload.account_id,
        operation_type="account_update",
        operation_key="preview",
        status="completed",
        severity="info",
        source="account_update_api",
        message="Account update preview built",
        workspace_id=workspace_id,
        metadata={
            "safety_blockers": preview.get("safety_blockers", []),
            "safety_warnings": preview.get("safety_warnings", []),
        },
    )
    session.commit()
    return AccountUpdatePreviewRead(**preview)


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


def create_job_use_case(
    session: Session,
    *,
    payload: AccountUpdateCreate,
    requested_by_user_id: str | None,
    workspace_id: str,
    config: Settings = settings,
) -> AccountUpdateJobSummaryRead:
    warmup_policy = warmup_service.warmup_operation_policy(
        session,
        account_id=payload.account_id,
        workspace_id=workspace_id,
        operation="profile_update",
    )
    if warmup_policy["is_locked"]:
        raise AccountWarmupLockedError(warmup_policy["reason"])

    job = create_job(
        session,
        account_id=payload.account_id,
        desired_state=payload.model_dump(exclude={"account_id"}, exclude_none=True),
        requested_by_user_id=requested_by_user_id,
        request_id=None,
        workspace_id=workspace_id,
        config=config,
    )
    log_operation(
        session,
        account_id=payload.account_id,
        operation_type="account_update",
        operation_key="create_job",
        status="completed",
        severity="info",
        source="account_update_api",
        message="Account update job created",
        job_id=job.id,
        workspace_id=workspace_id,
        metadata={"job_state": job.job_state},
    )
    session.commit()
    if job.job_state == JobState.QUEUED:
        log_event("account_update_enqueue_requested", account_id=payload.account_id, job_id=job.id)
        if enqueue_job(job.id) is False:
            if settings.queue_inline_fallback_enabled:
                log_event(
                    "account_update_inline_fallback_requested",
                    account_id=payload.account_id,
                    job_id=job.id,
                )
                execute_inline_fallback(job.id, session=session)
                session.refresh(job)
                return AccountUpdateJobSummaryRead(**job_summary(job))
            job.job_state = JobState.FAILED
            job.finished_at = utc_now()
            job.failure_reason = "enqueue_failed"
            session.commit()
            raise AccountQueueUnavailableError()
    return AccountUpdateJobSummaryRead(**job_summary(job))


def enqueue_job(job_id: str) -> bool:
    return enqueue_account_update_job(job_id)


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
    gate_verdict = evaluate_safety_gate(
        session,
        workspace_id=account.workspace_id,
        account_id=account_id,
        intent="editing",
    )
    if gate_verdict.severity == "blocked":
        blocking_errors.append(
            "safety_gate_blocked: " + "; ".join(reason.code for reason in gate_verdict.reasons)
        )
        safety_fields["safety_gate"] = {
            "severity": gate_verdict.severity,
            "reasons": [reason.model_dump(mode="json") for reason in gate_verdict.reasons],
        }
    elif gate_verdict.severity == "warning":
        warnings.append(
            "safety_gate_warning: " + "; ".join(reason.code for reason in gate_verdict.reasons)
        )
        safety_fields["safety_gate"] = {
            "severity": gate_verdict.severity,
            "reasons": [reason.model_dump(mode="json") for reason in gate_verdict.reasons],
        }

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
