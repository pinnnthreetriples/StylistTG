from __future__ import annotations

from http import HTTPStatus


class NeuroCommentingError(Exception):
    status_code: int = HTTPStatus.BAD_REQUEST
    error_code: str = "NEURO_COMMENTING_ERROR"
    error_class: str = "neuro_commenting"

    def __init__(self, message: str | None = None, *, error_code: str | None = None) -> None:
        super().__init__(message or self.error_code)
        if error_code is not None:
            self.error_code = error_code
        self.message = message or self.error_code


class NeuroNotFoundError(NeuroCommentingError):
    status_code = HTTPStatus.NOT_FOUND
    error_class = "not_found"


class NeuroValidationError(NeuroCommentingError):
    status_code = HTTPStatus.BAD_REQUEST
    error_class = "validation"


class NeuroConflictError(NeuroCommentingError):
    status_code = HTTPStatus.CONFLICT
    error_class = "conflict"


class NeuroRuntimeDisabledError(NeuroConflictError):
    error_class = "runtime_disabled"


class NeuroRuntimeUnavailableError(NeuroConflictError):
    error_class = "runtime_unavailable"


class NeuroRateLimiterNotReadyError(NeuroConflictError):
    error_code = "NEURO_COMMENT_RATE_LIMITER_NOT_READY"
    error_class = "rate_limiter"

    def __init__(self) -> None:
        super().__init__(
            "Neuro-comment sending requires Redis limiter.",
            error_code="NEURO_COMMENT_RATE_LIMITER_NOT_READY",
        )


def not_found(message: str, error_code: str) -> NeuroNotFoundError:
    return NeuroNotFoundError(message, error_code=error_code)
