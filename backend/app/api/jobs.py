from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.adapters.tdlib_profile_execution import build_profile_execution_adapter
from app.db import get_session
from app.errors import AppError
from app.logging_utils import log_event
from app.models import JobState, utc_now
from app.job_queue.rq import enqueue_profile_job, remove_job_from_queue
from app.schemas import (
    JobDetailRead,
    JobStepListItemRead,
    JobSummaryRead,
    ProfileJobCreate,
    ProfilePreviewRead,
    ProfilePreviewRequest,
    RetryPolicyRead,
)
from app.services.dashboard import job_summary
from app.api.tenant_helpers import require_account_in_workspace, require_job_in_workspace
from app.services.auth_context import (
    AuthContext,
    require_authenticated,
    require_mutation_permission,
)
from app.services.jobs import (
    build_job_detail,
    build_job_steps,
    build_profile_job_preview,
    cancel_job,
    create_profile_job,
    delete_job,
)
from app.services.runtime_settings import execution_policy_settings
from app.services.retry_policy import retry_policy_for

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/policies", response_model=dict[str, RetryPolicyRead])
def get_job_policies(_auth: AuthContext = Depends(require_authenticated)):
    return {
        category: RetryPolicyRead(
            retry=policy.retry,
            max_attempts=policy.max_attempts,
            interval_seconds=policy.interval_seconds,
            failure_ttl_seconds=policy.failure_ttl_seconds,
            result_ttl_seconds=policy.result_ttl_seconds,
            error_category=policy.error_category,
        )
        for category in (
            "flood_wait",
            "auth_required",
            "proxy_failed",
            "tdlib_unavailable",
            "validation_error",
            "unknown_transient",
        )
        for policy in (retry_policy_for(category),)
    }


@router.post("/profile/preview", response_model=ProfilePreviewRead)
def preview_profile_job(
    payload: ProfilePreviewRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, payload.account_id, auth)
    try:
        preview = build_profile_job_preview(
            session,
            account_id=payload.account_id,
            payload=payload.model_dump(exclude={"account_id"}, exclude_none=True),
            workspace_id=auth.workspace_id,
            config=execution_policy_settings(session),
        )
    except ValueError as exc:
        message = str(exc)
        error_code = "ACCOUNT_NOT_FOUND" if message == "account not found" else "VALIDATION_ERROR"
        error_class = "not_found" if message == "account not found" else "validation"
        field_errors: list[dict[str, str]] = []
        if "asset" in message:
            field_errors.append({"field": "photo_asset_id", "message": message})
        raise AppError(
            status_code=status.HTTP_400_BAD_REQUEST
            if error_class == "validation"
            else status.HTTP_404_NOT_FOUND,
            error_code=error_code,
            error_class=error_class,
            message=message,
            field_errors=field_errors,
        ) from exc
    return ProfilePreviewRead(**preview)


@router.post("/profile", response_model=JobSummaryRead, status_code=status.HTTP_201_CREATED)
def post_profile_job(
    payload: ProfileJobCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    data = payload.model_dump()
    account_id = data.pop("account_id")
    require_account_in_workspace(session, account_id, auth)
    try:
        job = create_profile_job(
            session,
            account_id=account_id,
            payload=data,
            execution_adapter=build_profile_execution_adapter(),
            requested_by_user_id=auth.user_id,
            workspace_id=auth.workspace_id,
            config=execution_policy_settings(session),
        )
    except ValueError as exc:
        message = str(exc)
        error_code = "ACCOUNT_NOT_FOUND" if message == "account not found" else "VALIDATION_ERROR"
        error_class = "not_found" if message == "account not found" else "validation"
        field_errors: list[dict[str, str]] = []
        if "asset" in message:
            field_errors.append({"field": "photo_asset_id", "message": message})
        if "execution_usable" in message:
            error_code = "RUNTIME_UNUSABLE"
            error_class = "runtime"
        if "manual intervention" in message:
            error_code = "ACCOUNT_MANUAL_INTERVENTION_REQUIRED"
            error_class = "runtime"
        if "cooldown" in message:
            error_code = "PROFILE_JOB_COOLDOWN_ACTIVE"
            error_class = "rate_limit"
        raise AppError(
            status_code=status.HTTP_400_BAD_REQUEST
            if error_class != "not_found"
            else status.HTTP_404_NOT_FOUND,
            error_code=error_code,
            error_class=error_class,
            message=message,
            field_errors=field_errors,
        ) from exc
    if job.job_state == JobState.QUEUED:
        log_event("job_enqueue_requested", account_id=account_id, job_id=job.id)
        if enqueue_profile_job(job.id) is False:
            job.job_state = JobState.FAILED
            job.finished_at = utc_now()
            job.failure_reason = "enqueue_failed"
            session.commit()
            raise AppError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                error_code="QUEUE_UNAVAILABLE",
                error_class="queue",
                message="job queue is unavailable",
            )
    return JobSummaryRead(**job_summary(job))


@router.get("/{job_id}", response_model=JobDetailRead)
def get_job_endpoint(
    job_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    job = require_job_in_workspace(session, job_id, auth)
    return JobDetailRead(**build_job_detail(job))


@router.get("/{job_id}/steps", response_model=list[JobStepListItemRead])
def get_job_steps_endpoint(
    job_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    job = require_job_in_workspace(session, job_id, auth)
    return [JobStepListItemRead(**step) for step in build_job_steps(job)]


@router.post("/{job_id}/cancel", response_model=JobSummaryRead)
def cancel_job_endpoint(
    job_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    require_job_in_workspace(session, job_id, auth)
    try:
        job = cancel_job(session, job_id)
    except ValueError as exc:
        raise _job_state_error(exc) from exc
    remove_job_from_queue(job_id)
    return JobSummaryRead(**job_summary(job))


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job_endpoint(
    job_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    require_job_in_workspace(session, job_id, auth)
    try:
        delete_job(session, job_id)
    except ValueError as exc:
        raise _job_state_error(exc) from exc
    remove_job_from_queue(job_id)


def _job_state_error(exc: ValueError) -> AppError:
    message = str(exc)
    if message == "job not found":
        return AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="JOB_NOT_FOUND",
            error_class="not_found",
            message=message,
        )
    if message == "running job cannot be canceled":
        return AppError(
            status_code=status.HTTP_409_CONFLICT,
            error_code="JOB_RUNNING_CANNOT_CANCEL",
            error_class="job_state",
            message=message,
        )
    if message == "active job cannot be deleted":
        return AppError(
            status_code=status.HTTP_409_CONFLICT,
            error_code="JOB_ACTIVE_CANNOT_DELETE",
            error_class="job_state",
            message=message,
        )
    return AppError(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_code="JOB_STATE_ERROR",
        error_class="job_state",
        message=message,
    )
