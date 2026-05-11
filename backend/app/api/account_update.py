from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.adapters.tdlib_profile_execution import build_profile_execution_adapter
from app.db import get_session
from app.errors import AppError
from app.job_queue.rq import enqueue_account_update_job
from app.logging_utils import log_event
from app.models import JobState, utc_now
from app.schemas import AccountUpdateCreate, AccountUpdateJobSummaryRead, AccountUpdatePreviewRead
from app.services.account_update_jobs import build_account_update_preview, create_account_update_job
from app.api.tenant_helpers import require_account_in_workspace
from app.services.auth_context import (
    AuthContext,
    require_authenticated,
    require_mutation_permission,
)
from app.services.dashboard import job_summary
from app.services.operation_logs import log_operation
from app.services.warmup import warmup_operation_policy
from app.config import settings
from app.workers.account_update_jobs import execute_account_update_job

router = APIRouter(prefix="/api/account-update", tags=["account-update"])


@router.post("/preview", response_model=AccountUpdatePreviewRead)
def preview_account_update(
    payload: AccountUpdateCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, payload.account_id, auth)
    try:
        preview = build_account_update_preview(
            session,
            account_id=payload.account_id,
            desired_state=payload.model_dump(exclude={"account_id"}, exclude_none=True),
            workspace_id=auth.workspace_id,
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
            workspace_id=auth.workspace_id,
            metadata={
                "safety_blockers": preview.get("safety_blockers", []),
                "safety_warnings": preview.get("safety_warnings", []),
            },
        )
        session.commit()
    except ValueError as exc:
        raise _account_update_error(exc) from exc
    return AccountUpdatePreviewRead(**preview)


@router.post(
    "/jobs", response_model=AccountUpdateJobSummaryRead, status_code=status.HTTP_201_CREATED
)
def post_account_update_job(
    payload: AccountUpdateCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    require_account_in_workspace(session, payload.account_id, auth)
    warmup_policy = warmup_operation_policy(
        session,
        account_id=payload.account_id,
        workspace_id=auth.workspace_id,
        operation="profile_update",
    )
    if warmup_policy["is_locked"]:
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            error_code="ACCOUNT_WARMUP_LOCKED",
            error_class="state_conflict",
            message=warmup_policy["reason"],
        )
    try:
        job = create_account_update_job(
            session,
            account_id=payload.account_id,
            desired_state=payload.model_dump(exclude={"account_id"}, exclude_none=True),
            execution_adapter=build_profile_execution_adapter(),
            requested_by_user_id=auth.user_id,
            request_id=None,
            workspace_id=auth.workspace_id,
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
            workspace_id=auth.workspace_id,
            metadata={"job_state": job.job_state},
        )
        session.commit()
    except ValueError as exc:
        raise _account_update_error(exc) from exc
    if job.job_state == JobState.QUEUED:
        log_event("account_update_enqueue_requested", account_id=payload.account_id, job_id=job.id)
        if enqueue_account_update_job(job.id) is False:
            if settings.queue_inline_fallback_enabled:
                log_event(
                    "account_update_inline_fallback_requested",
                    account_id=payload.account_id,
                    job_id=job.id,
                )
                execute_account_update_job(job.id, session=session)
                session.refresh(job)
                return AccountUpdateJobSummaryRead(**job_summary(job))
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
    return AccountUpdateJobSummaryRead(**job_summary(job))


def _account_update_error(exc: ValueError) -> AppError:
    message = str(exc)
    error_code = "ACCOUNT_NOT_FOUND" if message == "account not found" else "VALIDATION_ERROR"
    error_class = "not_found" if message == "account not found" else "validation"
    field_errors: list[dict[str, str]] = []
    if "story" in message and "asset" in message:
        error_code = "STORY_ASSET_NOT_READY"
        field_errors.append({"field": "stories", "message": message})
    elif "asset" in message:
        field_errors.append({"field": "photo_asset_id", "message": message})
    if "execution_usable" in message:
        error_code = "RUNTIME_UNUSABLE"
        error_class = "runtime"
    if message == "profile audio must be MP3 or M4A":
        error_code = "PROFILE_AUDIO_UNSUPPORTED_FORMAT"
        field_errors.append({"field": "profile_audio", "message": message})
    if "manual intervention" in message:
        error_code = "ACCOUNT_MANUAL_INTERVENTION_REQUIRED"
        error_class = "runtime"
    if "cooldown" in message:
        error_code = "PROFILE_JOB_COOLDOWN_ACTIVE"
        error_class = "rate_limit"
    if "stories are disabled" in message:
        error_code = "STORIES_DISABLED"
        error_class = "capability"
    if "stories live TDLib execution is not enabled" in message:
        error_code = "STORIES_TDLIB_LIVE_DISABLED"
        error_class = "capability"
    return AppError(
        status_code=status.HTTP_400_BAD_REQUEST
        if error_class != "not_found"
        else status.HTTP_404_NOT_FOUND,
        error_code=error_code,
        error_class=error_class,
        message=message,
        field_errors=field_errors,
    )
