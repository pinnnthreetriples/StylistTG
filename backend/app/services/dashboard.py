from __future__ import annotations

from sqlalchemy.orm import Session

from app.logging_utils import log_event, log_warn
from app.config import settings
from app.models import Job, JobState, TERMINAL_JOB_STATES
from app.services.account_bundle import get_account_dashboard_bundle, get_latest_job_for_account
from app.services.runtime_diagnostics import account_runtime_diagnostics
from app.services.profile_audio_state import profile_audio_state_payload
from app.services.profile_photo_state import latest_applied_profile_photo_asset_id
from app.services.story_posts import list_story_posts, story_post_payload

def build_dashboard_profile(session: Session, account_id: str) -> dict:
    account = get_account_dashboard_bundle(session, account_id)
    if account is None:
        log_warn("dashboard_account_not_found", account_id=account_id)
        raise ValueError("account not found")

    log_event("dashboard_build", account_id=account_id, state=account.account_state)

    latest_job = get_latest_job_for_account(session, account_id)
    runtime = account_runtime_diagnostics(session, account_id)
    profile_state = account.profile_state

    display_name = _compose_display_name(
        profile_state.first_name if profile_state else None,
        profile_state.last_name if profile_state else None,
    )
    synced_photo_asset_id = profile_state.profile_photo_asset_id if profile_state else None
    profile_photo_asset_id = synced_photo_asset_id or latest_applied_profile_photo_asset_id(session, account_id)
    latest_job_summary = job_summary(latest_job) if latest_job else None
    story_posts = list_story_posts(session, account_id)
    real_execution_enabled = settings.profile_execution_adapter == "tdlib"

    return {
        "account": {
            "account_id": account.id,
            "display_name": display_name,
            "username": profile_state.username if profile_state else None,
            "phone_number": account.external_ref,
            "telegram_user_id": account.telegram_user_id,
            "account_state": account.account_state,
            "runtime_health": account.runtime_state.runtime_health,
            "reauth_required": account.runtime_state.reauth_required,
            "is_execution_usable": account.account_state == "execution_usable",
        },
        "current_profile": {
            "first_name": profile_state.first_name if profile_state else None,
            "last_name": profile_state.last_name if profile_state else None,
            "bio": profile_state.bio if profile_state else None,
            "username": profile_state.username if profile_state else None,
            "profile_photo_asset_id": profile_photo_asset_id,
        },
        "profile_audio": profile_audio_state_payload(account.profile_audio_state),
        "story_posts": [story_post_payload(post) for post in story_posts],
        "editable_fields": {
            "name": display_name,
            "bio": profile_state.bio if profile_state else None,
            "username": profile_state.username if profile_state else None,
            "profile_photo": profile_photo_asset_id,
        },
        "pipeline": {
            "latest_job": latest_job_summary,
            "latest_job_state": latest_job.job_state if latest_job else None,
            "latest_job_id": latest_job.id if latest_job else None,
            "latest_job_finished_at": latest_job.finished_at if latest_job else None,
            "has_active_job": bool(latest_job and latest_job.job_state not in {state.value for state in TERMINAL_JOB_STATES}),
            "unsaved_changes_supported": True,
        },
        "diagnostics": {
            "last_error_code": runtime["last_error_code"],
            "last_error_class": runtime["last_error_class"],
            "authorized_last_confirmed_at": runtime["authorized_last_confirmed_at"],
            "real_execution_enabled": real_execution_enabled,
            "stories_live_execution_enabled": (
                real_execution_enabled and settings.stories_enabled and settings.stories_tdlib_live_enabled
            ),
        },
    }


def job_summary(job: Job) -> dict:
    return {
        "job_id": job.id,
        "job_state": job.job_state,
        "workflow_type": job.workflow_type,
        "workflow_version": job.workflow_version,
        "execution_intent_hash": job.execution_intent_hash,
        "plan_summary": [step["step_key"] for step in job.plan_json_snapshot.get("steps", [])],
        "created_at": job.queued_at,
        "dedup_blocked_by_job_id": job.dedup_blocked_by_job_id,
        "message": (
            "job deduplicated by active execution intent"
            if job.job_state == JobState.DEDUP_BLOCKED
            else None
        ),
    }


def _compose_display_name(first_name: str | None, last_name: str | None) -> str | None:
    parts = [(first_name or "").strip(), (last_name or "").strip()]
    value = " ".join(part for part in parts if part)
    return value or None
