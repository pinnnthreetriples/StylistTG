# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingTypeArgument=false, reportMissingParameterType=false, reportArgumentType=false
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.ai_profile_provider import (
    AIProfileProvider,
    AIProfileProviderError,
    AvatarGenerationRequest,
    BioGenerationRequest,
    GeneratedAvatar,
    GeneratedBio,
    build_ai_profile_provider,
)
from app.config import Settings, settings
from app.models import AccountOperationLog, utc_now
from app.modules.account_editing.uniqueness_check import (
    compute_photo_perceptual_hash_from_bytes,
    evaluate_profile_uniqueness,
    profile_uniqueness_payload,
)
from app.services.operation_logs import log_operation

OPERATION_TYPE = "ai_profile_generation"


@dataclass(frozen=True)
class GeneratedBioResult:
    bio: str
    provider: str
    model: str
    attempts: int
    uniqueness: dict


@dataclass(frozen=True)
class GeneratedAvatarResult:
    content: bytes
    provider: str
    model: str
    mime: str
    attempts: int
    uniqueness: dict


class AIProfileGenerationError(RuntimeError):
    def __init__(self, error_code: str, message: str, *, error_class: str = "ai_profile") -> None:
        super().__init__(message)
        self.error_code = error_code
        self.error_class = error_class


class AIProfileRateLimitError(AIProfileGenerationError):
    def __init__(self, message: str) -> None:
        super().__init__("AI_PROFILE_RATE_LIMITED", message, error_class="rate_limit")


def generate_unique_bio(
    session: Session,
    workspace_id: str,
    *,
    account_id: str,
    language: str,
    persona_hints: dict[str, str] | None = None,
    provider: AIProfileProvider | None = None,
    config: Settings = settings,
) -> GeneratedBioResult:
    hints = _normalize_hints(persona_hints)
    _enforce_rate_limits(session, workspace_id=workspace_id, account_id=account_id, config=config)
    active_provider = provider or build_ai_profile_provider(config)
    max_attempts = config.ai_profile_max_attempts
    for attempt in range(max_attempts):
        generated = _generate_bio(
            active_provider,
            BioGenerationRequest(
                workspace_id=workspace_id,
                account_id=account_id,
                language=language,
                persona_hints=hints,
                attempt=attempt,
            ),
        )
        uniqueness = evaluate_profile_uniqueness(
            session,
            workspace_id=workspace_id,
            bio=generated.text,
            photo_hash=None,
            exclude_account_id=account_id,
            threshold=config.ai_profile_uniqueness_threshold,
        )
        if not uniqueness.matches:
            _log_generation_success(
                session,
                workspace_id=workspace_id,
                account_id=account_id,
                kind="bio",
                provider=generated.provider,
                model=generated.model,
                attempts=attempt + 1,
            )
            return GeneratedBioResult(
                bio=generated.text,
                provider=generated.provider,
                model=generated.model,
                attempts=attempt + 1,
                uniqueness=profile_uniqueness_payload(uniqueness),
            )
    raise AIProfileGenerationError(
        "AI_PROFILE_UNIQUENESS_EXHAUSTED",
        f"Could not generate unique bio after {max_attempts} attempts",
        error_class="uniqueness",
    ) from None


def generate_unique_avatar(
    session: Session,
    workspace_id: str,
    *,
    account_id: str,
    persona_hints: dict[str, str] | None = None,
    provider: AIProfileProvider | None = None,
    config: Settings = settings,
) -> GeneratedAvatarResult:
    hints = _normalize_hints(persona_hints)
    _enforce_rate_limits(session, workspace_id=workspace_id, account_id=account_id, config=config)
    active_provider = provider or build_ai_profile_provider(config)
    max_attempts = config.ai_profile_max_attempts
    for attempt in range(max_attempts):
        generated = _generate_avatar(
            active_provider,
            AvatarGenerationRequest(
                workspace_id=workspace_id,
                account_id=account_id,
                persona_hints=hints,
                attempt=attempt,
            ),
        )
        photo_hash = compute_photo_perceptual_hash_from_bytes(generated.content)
        uniqueness = evaluate_profile_uniqueness(
            session,
            workspace_id=workspace_id,
            bio=None,
            photo_hash=photo_hash,
            exclude_account_id=account_id,
            threshold=config.ai_profile_uniqueness_threshold,
        )
        if not uniqueness.matches:
            _log_generation_success(
                session,
                workspace_id=workspace_id,
                account_id=account_id,
                kind="avatar",
                provider=generated.provider,
                model=generated.model,
                attempts=attempt + 1,
            )
            return GeneratedAvatarResult(
                content=generated.content,
                provider=generated.provider,
                model=generated.model,
                mime=generated.mime,
                attempts=attempt + 1,
                uniqueness=profile_uniqueness_payload(uniqueness),
            )
    raise AIProfileGenerationError(
        "AI_PROFILE_UNIQUENESS_EXHAUSTED",
        f"Could not generate unique avatar after {max_attempts} attempts",
        error_class="uniqueness",
    )


def _generate_bio(provider: AIProfileProvider, request: BioGenerationRequest) -> GeneratedBio:
    try:
        return provider.generate_bio(request)
    except AIProfileProviderError as exc:
        raise AIProfileGenerationError(exc.error_code, str(exc), error_class="provider") from exc


def _generate_avatar(
    provider: AIProfileProvider,
    request: AvatarGenerationRequest,
) -> GeneratedAvatar:
    try:
        return provider.generate_avatar(request)
    except AIProfileProviderError as exc:
        raise AIProfileGenerationError(exc.error_code, str(exc), error_class="provider") from exc


def _enforce_rate_limits(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    config: Settings,
) -> None:
    since = utc_now() - timedelta(days=1)
    workspace_count = _generation_count(session, workspace_id=workspace_id, since=since)
    if workspace_count >= config.ai_profile_workspace_daily_limit:
        raise AIProfileRateLimitError("Workspace AI profile generation daily limit reached")
    account_count = _generation_count(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        since=since,
    )
    if account_count >= config.ai_profile_account_daily_limit:
        raise AIProfileRateLimitError("Account AI profile generation daily limit reached")


def _generation_count(
    session: Session,
    *,
    workspace_id: str,
    since,
    account_id: str | None = None,
) -> int:
    query = select(func.count(AccountOperationLog.id)).where(
        AccountOperationLog.workspace_id == workspace_id,
        AccountOperationLog.operation_type == OPERATION_TYPE,
        AccountOperationLog.status == "completed",
        AccountOperationLog.created_at >= since,
    )
    if account_id is not None:
        query = query.where(AccountOperationLog.account_id == account_id)
    return int(session.execute(query).scalar_one())


def _log_generation_success(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    kind: str,
    provider: str,
    model: str,
    attempts: int,
) -> None:
    log_operation(
        session,
        account_id=account_id,
        workspace_id=workspace_id,
        operation_type=OPERATION_TYPE,
        operation_key=kind,
        status="completed",
        source="ai_profile_generation",
        message=f"Generated AI profile {kind}",
        metadata={
            "kind": kind,
            "provider": provider,
            "model": model,
            "attempts": attempts,
        },
    )


def _normalize_hints(persona_hints: dict[str, str] | None) -> dict[str, str]:
    return {
        str(key): str(value)
        for key, value in (persona_hints or {}).items()
        if str(key).strip() and str(value).strip()
    }
