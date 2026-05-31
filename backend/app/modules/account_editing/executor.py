from __future__ import annotations

from typing import Any, cast

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Job, JobState, StepStatus, TERMINAL_JOB_STATES
from app.services.jobs import get_job
from app.services.operation_logs import log_operation
from app.modules.account_profile_state.interfaces import (
    clear_profile_audio_state,
    upsert_profile_audio_state,
)
from app.modules.story.interfaces import (
    create_story_post_from_result,
    delete_story_drafts_for_asset,
)
from app.services.step_registry import validate_account_update_plan_steps
from app.workers.profile_jobs import execute_profile_job


def execute_account_update_job(job_id: str, *, session: Session | None = None) -> int:
    owns_session = session is None
    db_session = session or SessionLocal()
    try:
        return _execute_account_update_job(job_id, db_session)
    finally:
        if owns_session:
            db_session.close()


def _execute_account_update_job(job_id: str, session: Session) -> int:
    job = get_job(session, job_id)
    if job is None:
        return 1
    if job.job_state in TERMINAL_JOB_STATES:
        return 0
    validate_account_update_plan_steps(job.plan_json_snapshot)
    exit_code = execute_profile_job(job_id, session=session)
    job = get_job(session, job_id)
    if job is not None:
        _materialize_profile_audio(session, job)
        _materialize_story_posts(session, job)
        log_operation(
            session,
            account_id=job.account_id,
            operation_type="account_update",
            operation_key="job_terminal",
            status=str(job.job_state),
            severity="info"
            if job.job_state in {JobState.COMPLETED, JobState.PARTIALLY_COMPLETED}
            else "warning",
            source="account_update_worker",
            message="Account update job finished",
            job_id=job.id,
            workspace_id=job.workspace_id,
            metadata={"job_state": job.job_state, "failure_reason": job.failure_reason},
        )
        session.commit()
    return exit_code


# Legacy alias kept for the worker re-export module and tests that assert
# symbol identity across the worker boundary.
run_account_update_job = execute_account_update_job


def rematerialize_account_update_job(job_id: str, *, session: Session | None = None) -> bool:
    owns_session = session is None
    db_session = session or SessionLocal()
    try:
        job = get_job(db_session, job_id)
        if job is None:
            return False
        if job.job_state not in {JobState.COMPLETED, JobState.PARTIALLY_COMPLETED}:
            return False
        _materialize_profile_audio(db_session, job)
        _materialize_story_posts(db_session, job)
        db_session.commit()
        return True
    finally:
        if owns_session:
            db_session.close()


def _materialize_profile_audio(session: Session, job: Job) -> None:
    if job.workflow_type != "account_update":
        return
    if job.job_state not in {JobState.COMPLETED, JobState.PARTIALLY_COMPLETED}:
        return
    for step in job.step_results:
        if step.status != StepStatus.SUCCEEDED:
            continue
        payload = step.result_payload_json or {}
        profile_audio = payload.get("profile_audio")
        if step.step_type == "add_profile_audio" and isinstance(profile_audio, dict):
            audio = cast(dict[str, Any], profile_audio)
            upsert_profile_audio_state(
                session,
                account_id=job.account_id,
                telegram_file_id=audio.get("telegram_file_id"),
                source_asset_id=audio.get("source_asset_id"),
                title=audio.get("title"),
                performer=audio.get("performer"),
                duration_seconds=audio.get("duration_seconds"),
                mime=audio.get("mime"),
                telegram_audio_id=audio.get("telegram_audio_id"),
                raw_tdlib_json=audio.get("raw_tdlib_json"),
            )
        elif step.step_type == "remove_profile_audio" and payload.get("profile_audio_removed"):
            clear_profile_audio_state(session, account_id=job.account_id)


def _materialize_story_posts(session: Session, job: Job) -> None:
    if job.workflow_type != "account_update":
        return
    if job.job_state not in {JobState.COMPLETED, JobState.PARTIALLY_COMPLETED}:
        return
    for step in job.step_results:
        if step.status != StepStatus.SUCCEEDED:
            continue
        payload = step.result_payload_json or {}
        story = payload.get("story_post")
        if isinstance(story, dict):
            story_payload = cast(dict[str, Any], story)
            create_story_post_from_result(
                session,
                account_id=job.account_id,
                job_id=job.id,
                step_key=step.step_key,
                story=story_payload,
            )
            asset_id = story_payload.get("asset_id")
            if isinstance(asset_id, str):
                delete_story_drafts_for_asset(session, account_id=job.account_id, asset_id=asset_id)
