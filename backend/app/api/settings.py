from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import ExecutionPolicyRead, ExecutionPolicyUpdate
from app.services.auth_context import AuthContext, require_authenticated, require_role
from app.services.runtime_settings import get_execution_policy, update_execution_policy

router = APIRouter(prefix="/api/settings", tags=["settings"])

ALLOWED_PROFILE_JOB_COOLDOWNS_SECONDS = [30, 60, 120, 300, 600]
NON_OVERRIDABLE_BLOCKERS = [
    "SESSION_REVOKED",
    "AUTH_KEY_UNREGISTERED",
    "PHONE_NUMBER_BANNED",
    "missing_tdlib_credentials",
    "runtime_broken",
    "reauth_required",
]


@router.get("/execution-policy", response_model=ExecutionPolicyRead)
def get_execution_policy_endpoint(
    session: Session = Depends(get_session),
    _auth: AuthContext = Depends(require_authenticated),
):
    return _execution_policy_response(get_execution_policy(session))


@router.patch("/execution-policy", response_model=ExecutionPolicyRead)
def patch_execution_policy(
    payload: ExecutionPolicyUpdate,
    session: Session = Depends(get_session),
    _auth: AuthContext = Depends(require_role("admin")),
):
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        if key == "profile_job_cooldown_seconds" and not _is_valid_profile_job_cooldown(int(value)):
            raise HTTPException(
                status_code=422,
                detail="profile_job_cooldown_seconds must be 0 or between 30 and 600",
            )
        if (
            key != "profile_job_cooldown_seconds"
            and key.endswith("_cooldown_seconds")
            and not _is_valid_cooldown(int(value))
        ):
            raise HTTPException(status_code=422, detail=f"{key} must be 0 or between 30 and 86400")
        if key == "fresh_validity_max_age_minutes" and not 1 <= int(value) <= 1440:
            raise HTTPException(
                status_code=422, detail="fresh_validity_max_age_minutes must be between 1 and 1440"
            )
    return _execution_policy_response(update_execution_policy(session, values))


def _execution_policy_response(policy: dict[str, object]) -> ExecutionPolicyRead:
    return ExecutionPolicyRead(
        profile_job_cooldown_seconds=int(policy["profile_job_cooldown_seconds"]),
        profile_job_cooldown_enabled=int(policy["profile_job_cooldown_seconds"]) > 0,
        allowed_profile_job_cooldown_seconds=ALLOWED_PROFILE_JOB_COOLDOWNS_SECONDS,
        profile_update_cooldown_seconds=int(policy["profile_update_cooldown_seconds"]),
        username_cooldown_seconds=int(policy["username_cooldown_seconds"]),
        profile_photo_cooldown_seconds=int(policy["profile_photo_cooldown_seconds"]),
        profile_music_cooldown_seconds=int(policy["profile_music_cooldown_seconds"]),
        story_post_cooldown_seconds=int(policy["story_post_cooldown_seconds"]),
        story_delete_cooldown_seconds=int(policy["story_delete_cooldown_seconds"]),
        unknown_capability_policy=str(policy["unknown_capability_policy"]),
        recent_failure_policy=str(policy["recent_failure_policy"]),
        fresh_validity_required=str(policy["fresh_validity_required"]),
        fresh_validity_max_age_minutes=int(policy["fresh_validity_max_age_minutes"]),
        manual_hard_blocker_override_enabled=bool(
            policy["manual_hard_blocker_override_enabled"]
        ),
        non_overridable_blockers=NON_OVERRIDABLE_BLOCKERS,
    )


def _is_valid_profile_job_cooldown(value: int) -> bool:
    return _is_valid_cooldown(value) and value <= 600


def _is_valid_cooldown(value: int) -> bool:
    return value == 0 or 30 <= value <= 86400
