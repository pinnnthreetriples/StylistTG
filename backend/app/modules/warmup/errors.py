from __future__ import annotations


class WarmupError(ValueError):
    """Base typed error for warmup use cases."""

    def __init__(
        self,
        legacy_message: str,
        *,
        error_code: str = "WARMUP_SESSION_REJECTED",
        error_class: str = "validation",
        status_code: int | None = None,
        field_errors: tuple[dict[str, str], ...] = (),
    ) -> None:
        super().__init__(legacy_message)
        self.legacy_message = legacy_message
        self.error_code = error_code
        self.error_class = error_class
        self.status_code = status_code
        self.field_errors = field_errors

    def __str__(self) -> str:
        return self.legacy_message


class WarmupSessionNotFoundError(WarmupError):
    def __init__(self, legacy_message: str = "session not found") -> None:
        super().__init__(
            legacy_message,
            error_code="WARMUP_SESSION_NOT_FOUND",
            error_class="not_found",
            status_code=404,
        )


class WarmupStrategyNotFoundError(WarmupError):
    def __init__(self, legacy_message: str = "strategy not found") -> None:
        super().__init__(
            legacy_message,
            error_code="WARMUP_STRATEGY_NOT_FOUND",
            error_class="not_found",
            status_code=404,
        )


class WarmupSessionRejectedError(WarmupError):
    def __init__(self, legacy_message: str) -> None:
        super().__init__(
            legacy_message,
            error_code="WARMUP_SESSION_REJECTED",
            error_class="validation",
            status_code=422,
        )


class WarmupPauseRejectedError(WarmupError):
    def __init__(self, legacy_message: str = "session cannot be paused") -> None:
        super().__init__(
            legacy_message,
            error_code="WARMUP_PAUSE_REJECTED",
            error_class="state_conflict",
            status_code=409,
        )


class WarmupResumeRejectedError(WarmupError):
    def __init__(self, legacy_message: str = "session cannot be resumed") -> None:
        super().__init__(
            legacy_message,
            error_code="WARMUP_RESUME_REJECTED",
            error_class="state_conflict",
            status_code=409,
        )


class WarmupQueueUnavailableError(WarmupError):
    def __init__(self, legacy_message: str = "warmup queue is unavailable") -> None:
        super().__init__(
            legacy_message,
            error_code="WARMUP_QUEUE_UNAVAILABLE",
            error_class="queue",
            status_code=503,
        )


class WarmupIsolationConflictError(WarmupError):
    def __init__(
        self,
        legacy_message: str = "account is already isolated by another warmup session",
    ) -> None:
        super().__init__(
            legacy_message,
            error_code="WARMUP_ISOLATION_CONFLICT",
            error_class="state_conflict",
            status_code=409,
        )


__all__ = [
    "WarmupError",
    "WarmupIsolationConflictError",
    "WarmupPauseRejectedError",
    "WarmupQueueUnavailableError",
    "WarmupResumeRejectedError",
    "WarmupSessionNotFoundError",
    "WarmupSessionRejectedError",
    "WarmupStrategyNotFoundError",
]
