"""Account editing API router.

Compatibility owner for app.api.account_update.
Do not add behavior to the legacy app.api wrapper.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.db import get_session
from app.errors import AppError
from app.modules.account_editing import service as account_editing_service
from app.modules.account_editing.contracts import (
    AccountUpdateCreate,
    AccountUpdateJobSummaryRead,
    AccountUpdatePreviewRead,
)
from app.modules.account_editing.errors import AccountEditingError
from app.modules.auth.dependencies import (
    AuthContext,
    require_authenticated,
    require_mutation_permission,
)
from app.services.runtime_settings import execution_policy_settings

router = APIRouter(prefix="/api/account-update", tags=["account-update"])


@router.post("/preview", response_model=AccountUpdatePreviewRead)
def preview_account_update(
    payload: AccountUpdateCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, payload.account_id, auth)
    try:
        return account_editing_service.build_preview_use_case(
            session,
            payload=payload,
            workspace_id=auth.workspace_id,
            config=execution_policy_settings(session),
        )
    except (AccountEditingError, ValueError) as exc:
        raise _account_update_error(exc) from exc


@router.post(
    "/jobs", response_model=AccountUpdateJobSummaryRead, status_code=status.HTTP_201_CREATED
)
def post_account_update_job(
    payload: AccountUpdateCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    require_account_in_workspace(session, payload.account_id, auth)
    try:
        return account_editing_service.create_job_use_case(
            session,
            payload=payload,
            workspace_id=auth.workspace_id,
            requested_by_user_id=auth.user_id,
            config=execution_policy_settings(session),
        )
    except (AccountEditingError, ValueError) as exc:
        raise _account_update_error(exc) from exc


def _account_update_error(exc: AccountEditingError | ValueError) -> AppError:
    if isinstance(exc, AccountEditingError):
        status_code = status.HTTP_400_BAD_REQUEST
        if exc.error_class == "not_found":
            status_code = status.HTTP_404_NOT_FOUND
        elif exc.error_code == "ACCOUNT_WARMUP_LOCKED":
            status_code = status.HTTP_409_CONFLICT
        elif exc.error_code == "QUEUE_UNAVAILABLE":
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return AppError(
            status_code=status_code,
            error_code=exc.error_code,
            error_class=exc.error_class,
            message=exc.legacy_message,
            field_errors=list(exc.field_errors),
        )

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
