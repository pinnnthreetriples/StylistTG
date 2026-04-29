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
from app.services.dashboard import job_summary
from app.config import settings
from app.workers.account_update_jobs import execute_account_update_job

router = APIRouter(prefix="/api/account-update", tags=["account-update"])


@router.post("/preview", response_model=AccountUpdatePreviewRead)
def preview_account_update(payload: AccountUpdateCreate, session: Session = Depends(get_session)):
    try:
        preview = build_account_update_preview(
            session,
            account_id=payload.account_id,
            desired_state=payload.model_dump(exclude={"account_id"}, exclude_none=True),
        )
    except ValueError as exc:
        raise _account_update_error(exc) from exc
    return AccountUpdatePreviewRead(**preview)


@router.post("/jobs", response_model=AccountUpdateJobSummaryRead, status_code=status.HTTP_201_CREATED)
def post_account_update_job(payload: AccountUpdateCreate, session: Session = Depends(get_session)):
    try:
        job = create_account_update_job(
            session,
            account_id=payload.account_id,
            desired_state=payload.model_dump(exclude={"account_id"}, exclude_none=True),
            execution_adapter=build_profile_execution_adapter(),
        )
    except ValueError as exc:
        raise _account_update_error(exc) from exc
    if job.job_state == JobState.QUEUED:
        log_event("account_update_enqueue_requested", account_id=payload.account_id, job_id=job.id)
        if enqueue_account_update_job(job.id) is False:
            if settings.queue_inline_fallback_enabled:
                log_event("account_update_inline_fallback_requested", account_id=payload.account_id, job_id=job.id)
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
    field_errors = []
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
        status_code=status.HTTP_400_BAD_REQUEST if error_class != "not_found" else status.HTTP_404_NOT_FOUND,
        error_code=error_code,
        error_class=error_class,
        message=message,
        field_errors=field_errors,
    )
