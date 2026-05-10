from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, JobState, JobStepResult, StepStatus


def latest_applied_profile_photo_asset_id(session: Session, account_id: str) -> str | None:
    statement = (
        select(JobStepResult.result_payload_json)
        .join(Job, Job.id == JobStepResult.job_id)
        .where(Job.account_id == account_id)
        .where(Job.job_state.in_([JobState.COMPLETED, JobState.PARTIALLY_COMPLETED]))
        .where(JobStepResult.step_type == "set_profile_photo")
        .where(JobStepResult.status == StepStatus.SUCCEEDED)
        .where(JobStepResult.result_payload_json.is_not(None))
        .order_by(JobStepResult.finished_at.desc(), Job.finished_at.desc())
        .limit(1)
    )
    payload = session.execute(statement).scalars().first()
    if not isinstance(payload, dict):
        return None
    return _extract_photo_asset_id(cast(dict[str, Any], payload))


def batch_latest_profile_photo_asset_ids(
    session: Session, account_ids: list[str]
) -> dict[str, str | None]:
    """Return {account_id: photo_asset_id} for a batch of accounts in one query."""
    if not account_ids:
        return {}
    statement = (
        select(Job.account_id, JobStepResult.result_payload_json)
        .join(Job, Job.id == JobStepResult.job_id)
        .where(Job.account_id.in_(account_ids))
        .where(Job.job_state.in_([JobState.COMPLETED, JobState.PARTIALLY_COMPLETED]))
        .where(JobStepResult.step_type == "set_profile_photo")
        .where(JobStepResult.status == StepStatus.SUCCEEDED)
        .where(JobStepResult.result_payload_json.is_not(None))
        .order_by(Job.account_id, JobStepResult.finished_at.desc(), Job.finished_at.desc())
    )
    rows = session.execute(statement).all()
    result: dict[str, str | None] = {}
    for account_id, payload in rows:
        if account_id not in result and isinstance(payload, dict):
            result[account_id] = _extract_photo_asset_id(cast(dict[str, Any], payload))
    return result


def _extract_photo_asset_id(payload: dict[str, Any]) -> str | None:
    applied = payload.get("applied")
    if isinstance(applied, dict):
        applied_payload = cast(dict[str, Any], applied)
        if isinstance(applied_payload.get("photo_asset_id"), str):
            return applied_payload["photo_asset_id"]
    if isinstance(payload.get("photo_asset_id"), str):
        return payload["photo_asset_id"]
    return None
