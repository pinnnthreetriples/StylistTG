from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.logging_utils import log_event
from app.models import AccountState, AssetKind, AssetStatus, Job, JobState, TERMINAL_JOB_STATES, utc_now
from app.services.audit_logs import log_audit_event
from app.services.limits import check_workspace_limit, increment_usage
from app.services.accounts import get_account
from app.services.assets import get_asset
from app.services.auth import is_account_hard_stopped
from app.services.execution_policy import ExecutionUsableAdapter, ensure_execution_usable
from app.services.plan import build_profile_plan, compute_execution_intent_hash
from app.services.asset_storage import materialize_asset_to_local_path


def find_active_duplicate_job(
    session: Session, account_id: str, execution_intent_hash: str
) -> Job | None:
    statement = (
        select(Job)
        .where(Job.account_id == account_id)
        .where(Job.execution_intent_hash == execution_intent_hash)
        .where(Job.job_state.not_in([state.value for state in TERMINAL_JOB_STATES]))
        .order_by(Job.queued_at.asc())
    )
    return session.execute(statement).scalars().first()


def create_profile_job(
    session: Session,
    *,
    account_id: str,
    payload: dict,
    execution_adapter: ExecutionUsableAdapter | None = None,
    config: Settings = settings,
    requested_by_user_id: str | None = None,
    created_from: str = "api",
    request_id: str | None = None,
    workspace_id: str | None = None,
) -> Job:
    account = get_account(session, account_id, workspace_id=workspace_id)
    if account is None:
        raise ValueError("account not found")
    if is_account_hard_stopped(account):
        raise ValueError("account requires manual intervention")

    if execution_adapter is not None:
        policy = ensure_execution_usable(session, account_id, adapter=execution_adapter)
        if not policy.ok or policy.account.account_state != AccountState.EXECUTION_USABLE:
            raise ValueError("account is not execution_usable")

    if is_profile_job_cooldown_active(session, account_id, config=config):
        raise ValueError("profile job cooldown active")
    check_workspace_limit(session, account.workspace_id, "jobs_per_day")

    payload = normalize_profile_payload(session, payload, workspace_id=account.workspace_id)
    intent_hash = compute_execution_intent_hash(account_id, payload)
    duplicate = find_active_duplicate_job(session, account_id, intent_hash)
    state = JobState.DEDUP_BLOCKED if duplicate else JobState.QUEUED
    job = Job(
        workspace_id=account.workspace_id,
        account_id=account_id,
        requested_by_user_id=requested_by_user_id,
        created_from=created_from,
        request_id=request_id,
        job_state=state,
        execution_intent_hash=intent_hash,
        job_payload_version=1,
        payload_json=payload,
        plan_json_snapshot=build_profile_plan(payload),
        dedup_blocked_by_job_id=duplicate.id if duplicate else None,
        queued_at=utc_now() if not duplicate else None,
    )
    session.add(job)
    log_audit_event(
        session,
        workspace_id=account.workspace_id,
        actor_user_id=requested_by_user_id,
        action="job.created",
        entity_type="job",
        entity_id=job.id,
        request_id=request_id,
        metadata={"workflow_type": job.workflow_type, "state": state},
    )
    if state == JobState.QUEUED:
        increment_usage(session, account.workspace_id, "jobs_per_day")
    session.commit()
    session.refresh(job)
    log_event(
        "job_created",
        job_id=job.id,
        account_id=account_id,
        state=job.job_state,
        intent_hash=intent_hash[:12],
        steps=len(job.plan_json_snapshot.get("steps", [])),
        dedup=duplicate.id if duplicate else None,
    )
    return job


def get_job(session: Session, job_id: str) -> Job | None:
    return session.get(Job, job_id)


def cancel_job(session: Session, job_id: str) -> Job:
    job = get_job(session, job_id)
    if job is None:
        raise ValueError("job not found")
    if job.job_state in TERMINAL_JOB_STATES:
        return job
    if job.job_state == JobState.RUNNING:
        raise ValueError("running job cannot be canceled")
    job.job_state = JobState.CANCELED
    job.finished_at = utc_now()
    job.failure_reason = "canceled_by_user"
    session.commit()
    session.refresh(job)
    return job


def delete_job(session: Session, job_id: str) -> None:
    job = get_job(session, job_id)
    if job is None:
        raise ValueError("job not found")
    if job.job_state not in TERMINAL_JOB_STATES:
        raise ValueError("active job cannot be deleted")
    session.delete(job)
    session.commit()


def normalize_profile_payload(session: Session, payload: dict, *, workspace_id: str | None = None) -> dict:
    normalized_payload = dict(payload)
    _validate_profile_asset(session, normalized_payload, workspace_id=workspace_id)
    return normalized_payload


def list_account_jobs(
    session: Session,
    account_id: str,
    *,
    limit: int = 10,
    workspace_id: str | None = None,
) -> list[Job]:
    statement = (
        select(Job)
        .where(Job.account_id == account_id)
        .order_by(Job.queued_at.desc(), Job.started_at.desc(), Job.finished_at.desc())
        .limit(limit)
    )
    if workspace_id is not None:
        statement = statement.where(Job.workspace_id == workspace_id)
    return list(session.execute(statement).scalars().all())


def get_latest_account_job(session: Session, account_id: str, *, workspace_id: str | None = None) -> Job | None:
    jobs = list_account_jobs(session, account_id, limit=1, workspace_id=workspace_id)
    return jobs[0] if jobs else None


def build_profile_job_preview(
    session: Session,
    *,
    account_id: str,
    payload: dict,
    workspace_id: str | None = None,
) -> dict:
    account = get_account(session, account_id, workspace_id=workspace_id)
    if account is None:
        raise ValueError("account not found")

    blocking_errors: list[str] = []
    warnings: list[str] = []
    normalized_payload = normalize_profile_payload(session, payload, workspace_id=account.workspace_id)
    intent_hash = compute_execution_intent_hash(account_id, normalized_payload)
    duplicate = find_active_duplicate_job(session, account_id, intent_hash)
    plan = build_profile_plan(normalized_payload)
    if is_account_hard_stopped(account):
        blocking_errors.append("account requires manual intervention")
    if account.account_state != AccountState.EXECUTION_USABLE:
        blocking_errors.append("account is not execution_usable")
    if is_profile_job_cooldown_active(session, account_id):
        blocking_errors.append("profile job cooldown active")

    return {
        "can_create_job": not blocking_errors,
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "normalized_payload": normalized_payload,
        "execution_intent_hash": intent_hash,
        "plan_json_snapshot": plan,
        "steps": plan["steps"],
        "requires_execution_usable": True,
        "dedup_would_block": duplicate is not None,
        "dedup_blocked_by_job_id": duplicate.id if duplicate else None,
    }


def build_job_detail(job: Job) -> dict:
    plan_steps = job.plan_json_snapshot.get("steps", [])
    counts = {status: 0 for status in ("planned", "started", "succeeded", "failed", "uncertain", "skipped")}
    for step_result in job.step_results:
        counts[step_result.status] += 1
    counts["planned"] = max(len(plan_steps) - sum(counts[status] for status in counts if status != "planned"), 0)
    return {
        "job_id": job.id,
        "job_state": job.job_state,
        "account_id": job.account_id,
        "execution_intent_hash": job.execution_intent_hash,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "failure_reason": job.failure_reason,
        "can_retry": False,
        "can_refresh_runtime": True,
        "step_counts": counts,
    }


def build_job_steps(job: Job) -> list[dict]:
    step_results_by_key = {step.step_key: step for step in job.step_results}
    ordered_steps: list[dict] = []
    for step in job.plan_json_snapshot.get("steps", []):
        result = step_results_by_key.get(step["step_key"])
        if result is None:
            continue
        ordered_steps.append(
            {
                "step_key": result.step_key,
                "step_type": result.step_type,
                "status": result.status,
                "verification_attempted": result.verification_attempted,
                "verification_result": result.verification_result,
                "uncertain_reason": result.uncertain_reason,
                "error_code": result.error_code,
                "error_class": result.error_class,
                "result_payload_json": result.result_payload_json,
                "started_at": result.started_at,
                "finished_at": result.finished_at,
            }
        )
    return ordered_steps


def _validate_profile_asset(session: Session, payload: dict, *, workspace_id: str | None = None) -> None:
    asset_id = payload.get("photo_asset_id")
    if not asset_id:
        return
    asset = get_asset(session, asset_id, workspace_id=workspace_id)
    if asset is None:
        raise ValueError("asset not found")
    if asset.kind != AssetKind.PROFILE_PHOTO:
        raise ValueError("asset kind is not profile_photo")
    if asset.status != AssetStatus.NORMALIZED:
        raise ValueError("asset is not ready for profile photo execution")
    payload["photo_asset_path"] = str(materialize_asset_to_local_path(asset, config=settings))


def is_profile_job_cooldown_active(
    session: Session,
    account_id: str,
    *,
    config: Settings = settings,
) -> bool:
    if config.profile_job_cooldown_seconds <= 0:
        return False
    cooldown_started_at = utc_now() - timedelta(seconds=config.profile_job_cooldown_seconds)
    recent_success = session.execute(
        select(Job.id)
        .where(Job.account_id == account_id)
        .where(Job.job_state.in_([JobState.COMPLETED, JobState.PARTIALLY_COMPLETED]))
        .where(Job.finished_at.is_not(None))
        .where(Job.finished_at >= cooldown_started_at)
        .order_by(Job.finished_at.desc())
    ).scalars().first()
    return recent_success is not None


