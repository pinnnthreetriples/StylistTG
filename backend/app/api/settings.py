from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas import ExecutionPolicyRead, ExecutionPolicyUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])

ALLOWED_PROFILE_JOB_COOLDOWNS_SECONDS = [30, 60, 120, 300, 600]


@router.get("/execution-policy", response_model=ExecutionPolicyRead)
def get_execution_policy():
    return _execution_policy_response()


@router.patch("/execution-policy", response_model=ExecutionPolicyRead)
def patch_execution_policy(payload: ExecutionPolicyUpdate):
    if not _is_valid_profile_job_cooldown(payload.profile_job_cooldown_seconds):
        raise HTTPException(
            status_code=422,
            detail="profile_job_cooldown_seconds must be 0 or between 30 and 600",
        )
    settings.profile_job_cooldown_seconds = payload.profile_job_cooldown_seconds
    return _execution_policy_response()


def _execution_policy_response() -> ExecutionPolicyRead:
    return ExecutionPolicyRead(
        profile_job_cooldown_seconds=settings.profile_job_cooldown_seconds,
        profile_job_cooldown_enabled=settings.profile_job_cooldown_seconds > 0,
        allowed_profile_job_cooldown_seconds=ALLOWED_PROFILE_JOB_COOLDOWNS_SECONDS,
    )


def _is_valid_profile_job_cooldown(value: int) -> bool:
    return value == 0 or 30 <= value <= 600
