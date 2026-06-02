from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any

from app.errors import AppError


def _empty_field_errors() -> list[dict[str, str]]:
    return []


@dataclass(slots=True)
class OnboardingError(Exception):
    code: str
    detail: str
    status_code: int = HTTPStatus.BAD_REQUEST
    title: str = "Account onboarding error"
    field_errors: list[dict[str, str]] = field(default_factory=_empty_field_errors)
    safe_details: dict[str, Any] | None = None


def to_app_error(exc: OnboardingError) -> AppError:
    return AppError(
        status_code=exc.status_code,
        error_code=exc.code,
        error_class="account_onboarding",
        message=exc.detail,
        details={
            "type": f"https://stylisttg.local/problems/{exc.code.lower()}",
            "title": exc.title,
            "status": exc.status_code,
            "detail": exc.detail,
            "code": exc.code,
            **(exc.safe_details or {}),
        },
        field_errors=exc.field_errors,
    )


def batch_not_found() -> OnboardingError:
    return OnboardingError(
        "ONBOARDING_BATCH_NOT_FOUND",
        "Account onboarding batch not found.",
        HTTPStatus.NOT_FOUND,
        "Batch not found",
    )


def item_not_found() -> OnboardingError:
    return OnboardingError(
        "ONBOARDING_ITEM_NOT_FOUND",
        "Account onboarding item not found.",
        HTTPStatus.NOT_FOUND,
        "Item not found",
    )


def invalid_state(detail: str) -> OnboardingError:
    return OnboardingError(
        "ONBOARDING_INVALID_STATE", detail, HTTPStatus.CONFLICT, "Invalid onboarding state"
    )


def consent_required() -> OnboardingError:
    return OnboardingError(
        "ONBOARDING_CONSENT_REQUIRED",
        "Explicit ADD_ACCOUNTS consent is required before account addition starts.",
        HTTPStatus.CONFLICT,
        "Consent required",
    )


def rate_limited(retry_after_seconds: int) -> OnboardingError:
    return OnboardingError(
        "ONBOARDING_RATE_LIMITED",
        "Account onboarding action is cooling down.",
        HTTPStatus.TOO_MANY_REQUESTS,
        "Rate limited",
        safe_details={"retry_after_seconds": retry_after_seconds},
    )


def unsupported_source(source_type: str) -> OnboardingError:
    return OnboardingError(
        "ONBOARDING_SOURCE_UNSUPPORTED",
        "Account onboarding source is unsupported.",
        safe_details={"source_type": source_type},
    )


def artifact_too_large(limit_bytes: int) -> OnboardingError:
    return OnboardingError(
        "ONBOARDING_ARTIFACT_TOO_LARGE",
        "Uploaded artifact is too large.",
        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        "Artifact too large",
        safe_details={"limit_bytes": limit_bytes},
    )


def artifact_unsafe(code: str, message: str) -> OnboardingError:
    return OnboardingError(
        "ONBOARDING_ARTIFACT_UNSAFE", message, safe_details={"validation_code": code}
    )


def queue_unavailable() -> OnboardingError:
    return OnboardingError(
        "ONBOARDING_QUEUE_UNAVAILABLE",
        "Account onboarding queue is unavailable.",
        HTTPStatus.SERVICE_UNAVAILABLE,
        "Queue unavailable",
    )
