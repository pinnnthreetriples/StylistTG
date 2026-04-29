from __future__ import annotations

from typing import Any

from app.models import JobState, StepStatus

ACCOUNT_UPDATE_STEP_TYPES = {
    "set_name",
    "set_bio",
    "set_username",
    "set_profile_photo",
    "upload_profile_audio",
    "add_profile_audio",
    "remove_profile_audio",
    "validate_story_capabilities",
    "prepare_story_media",
    "post_story_image",
    "post_story_video",
}

HARD_STOP_ERROR_MARKERS = {
    "FLOOD",
    "FROZEN",
    "PHONE_NUMBER_BANNED",
    "AUTH_KEY_UNREGISTERED",
    "SESSION_REVOKED",
    "REAUTH_REQUIRED",
    "RUNTIME_BROKEN",
    "MISSING_TDLIB_CREDENTIALS",
    "TDLIB_CLIENT_CLOSED_UNEXPECTEDLY",
    "ACCOUNT_LOCK_CORRUPTION",
}


def is_hard_stop_error(error_code: str | None) -> bool:
    if not error_code:
        return False
    normalized = error_code.upper()
    return any(marker in normalized for marker in HARD_STOP_ERROR_MARKERS)


def classify_account_update_job_outcome(
    step_results: list[dict[str, Any]], *, hard_stop_error_code: str | None = None
) -> JobState:
    if hard_stop_error_code:
        return JobState.MANUAL_INTERVENTION_NEEDED

    meaningful_success = any(result["status"] == StepStatus.SUCCEEDED for result in step_results)
    failed_results = [result for result in step_results if result["status"] == StepStatus.FAILED]
    if failed_results:
        known_failures = all(result["step_type"] in ACCOUNT_UPDATE_STEP_TYPES for result in failed_results)
        if meaningful_success and known_failures:
            return JobState.PARTIALLY_COMPLETED
        return JobState.FAILED

    if any(result["status"] == StepStatus.UNCERTAIN for result in step_results):
        return JobState.PARTIALLY_COMPLETED if meaningful_success else JobState.FAILED

    return JobState.COMPLETED
