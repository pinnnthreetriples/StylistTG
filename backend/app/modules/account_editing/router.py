# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingTypeArgument=false, reportMissingParameterType=false, reportArgumentType=false
"""Account editing API router.

Compatibility owner for app.api.account_update.
Do not add behavior to the legacy app.api wrapper.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.config import settings
from app.db import get_session
from app.errors import AppError
from app.modules.account_editing import ai_generation
from app.modules.account_editing import service as account_editing_service
from app.modules.account_editing.contracts import (
    AIProfileGenerateAvatarRead,
    AIProfileGenerateAvatarRequest,
    AIProfileGenerateBioRead,
    AIProfileGenerateBioRequest,
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
from app.services.assets import save_profile_photo_asset
from app.services.runtime_settings import execution_policy_settings

account_update_router = APIRouter(prefix="/api/account-update", tags=["account-update"])
profile_generation_router = APIRouter(prefix="/api/accounts", tags=["accounts"])
router = APIRouter()


@account_update_router.post("/preview", response_model=AccountUpdatePreviewRead)
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


@account_update_router.post(
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


@profile_generation_router.post(
    "/{account_id}/generate-bio",
    response_model=AIProfileGenerateBioRead,
)
def post_generate_bio(
    account_id: str,
    payload: AIProfileGenerateBioRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    require_account_in_workspace(session, account_id, auth)
    try:
        result = ai_generation.generate_unique_bio(
            session,
            auth.workspace_id,
            account_id=account_id,
            language=payload.language,
            persona_hints=payload.persona_hints,
            config=settings,
        )
        session.commit()
        return {
            "bio": result.bio,
            "provider": result.provider,
            "model": result.model,
            "attempts": result.attempts,
            "uniqueness": result.uniqueness,
        }
    except ai_generation.AIProfileGenerationError as exc:
        session.rollback()
        raise _ai_profile_error(exc) from exc


@profile_generation_router.post(
    "/{account_id}/generate-avatar",
    response_model=AIProfileGenerateAvatarRead,
)
def post_generate_avatar(
    account_id: str,
    payload: AIProfileGenerateAvatarRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    require_account_in_workspace(session, account_id, auth)
    try:
        result = ai_generation.generate_unique_avatar(
            session,
            auth.workspace_id,
            account_id=account_id,
            persona_hints=payload.persona_hints,
            config=settings,
        )
        asset = save_profile_photo_asset(
            session,
            filename=f"generated-avatar-{account_id}.png",
            content=result.content,
            storage_root=settings.storage_root,
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
        )
        return {
            "asset_id": asset.id,
            "provider": result.provider,
            "model": result.model,
            "mime": result.mime,
            "attempts": result.attempts,
            "uniqueness": result.uniqueness,
        }
    except (ai_generation.AIProfileGenerationError, ValueError) as exc:
        session.rollback()
        if isinstance(exc, ai_generation.AIProfileGenerationError):
            raise _ai_profile_error(exc) from exc
        raise _account_update_error(exc) from exc


def _ai_profile_error(exc: ai_generation.AIProfileGenerationError) -> AppError:
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.error_class == "rate_limit":
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
    elif exc.error_class == "provider":
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif exc.error_class == "uniqueness":
        status_code = status.HTTP_409_CONFLICT
    return AppError(
        status_code=status_code,
        error_code=exc.error_code,
        error_class=exc.error_class,
        message=str(exc),
        field_errors=[],
    )


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


router.include_router(account_update_router)
router.include_router(profile_generation_router)
