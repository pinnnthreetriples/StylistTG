from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models import ACTIVE_WARMUP_STATUSES, WarmupExecutionMode, WarmupStatus
from app.modules.warmup.errors import (
    WarmupPauseRejectedError,
    WarmupResumeRejectedError,
    WarmupSessionRejectedError,
)


def is_live_warmup_mode(execution_mode: str) -> bool:
    return execution_mode != WarmupExecutionMode.DRY_RUN.value


def is_warmup_active_status(status: str) -> bool:
    return status in {item.value for item in ACTIVE_WARMUP_STATUSES}


def can_create_warmup_session(blocking_reasons: list[str]) -> None:
    if blocking_reasons:
        raise WarmupSessionRejectedError("; ".join(blocking_reasons))


def can_pause_warmup_session(status: str) -> None:
    if status not in {WarmupStatus.SCHEDULED, WarmupStatus.ACTIVE}:
        raise WarmupPauseRejectedError()


def can_resume_warmup_session(
    status: str,
    *,
    next_attempt_at: datetime | None,
    now: datetime,
) -> None:
    if status not in {WarmupStatus.PAUSED_MANUAL, WarmupStatus.PAUSED_RISK}:
        raise WarmupResumeRejectedError()
    if next_attempt_at and next_attempt_at > now:
        raise WarmupResumeRejectedError(f"retry_not_ready:{next_attempt_at.isoformat()}")


def validate_session_status_transition(
    *,
    action: str,
    current_status: str,
    next_attempt_at: datetime | None = None,
    now: datetime | None = None,
) -> None:
    if action == "pause":
        can_pause_warmup_session(current_status)
        return
    if action == "resume":
        if now is None:
            raise WarmupResumeRejectedError()
        can_resume_warmup_session(current_status, next_attempt_at=next_attempt_at, now=now)
        return
    raise WarmupSessionRejectedError(f"unsupported warmup status transition: {action}")


def warmup_operation_policy(
    *,
    warmup_session: Any | None,
    operation: str,
) -> dict[str, Any]:
    locked_operations = {"profile_update", "proxy_change", "account_delete"}
    is_locked = warmup_session is not None and operation in locked_operations
    return {
        "session_id": warmup_session.id if warmup_session else None,
        "status": warmup_session.status if warmup_session else None,
        "current_day": warmup_session.current_day if warmup_session else None,
        "is_locked": is_locked,
        "reason": "Аккаунт находится в подготовке" if is_locked else None,
    }


__all__ = [
    "can_create_warmup_session",
    "can_pause_warmup_session",
    "can_resume_warmup_session",
    "is_live_warmup_mode",
    "is_warmup_active_status",
    "validate_session_status_transition",
    "warmup_operation_policy",
]
