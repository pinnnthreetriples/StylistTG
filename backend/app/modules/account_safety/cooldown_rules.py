"""Cooldown rule mapping and pure conversion helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re
from typing import Any

from app.config import Settings, settings
from app.models import AccountOperationCooldown, JobStepResult, utc_now

OPERATION_KEYS = (
    "profile_update",
    "username",
    "profile_photo",
    "profile_music",
    "story_post",
    "story_delete",
    "sync",
    "batch_operation",
)

STEP_OPERATION_MAP = {
    "set_name": "profile_update",
    "set_bio": "profile_update",
    "set_username": "username",
    "set_profile_photo": "profile_photo",
    "upload_profile_audio": "profile_music",
    "add_profile_audio": "profile_music",
    "remove_profile_audio": "profile_music",
    "post_story_image": "story_post",
    "post_story_video": "story_post",
    "delete_story": "story_delete",
}

FLOOD_WAIT_RE = re.compile(r"FLOOD_WAIT_?(?P<seconds>\d+)", re.IGNORECASE)


def cooldown_from_failed_step(
    step: JobStepResult, *, config: Settings = settings
) -> dict[str, Any] | None:
    error_code = step.error_code or ""
    match = FLOOD_WAIT_RE.search(error_code)
    operation = STEP_OPERATION_MAP.get(step.step_type, "profile_update")
    started_at = step.finished_at or step.started_at or utc_now()
    if not match:
        if config.recent_failure_policy != "cooldown":
            return None
        seconds = product_cooldown_seconds(operation, config=config)
        if seconds <= 0:
            return None
        return {
            "operation": operation,
            "level": "warning",
            "reason_code": "recent_failure_cooldown",
            "started_at": started_at,
            "retry_after_at": aware_datetime(started_at) + timedelta(seconds=seconds),
            "source": "job_step_result",
        }
    return {
        "operation": operation,
        "level": "blocked",
        "reason_code": "recent_flood_wait",
        "started_at": started_at,
        "retry_after_at": aware_datetime(started_at)
        + timedelta(seconds=int(match.group("seconds"))),
        "source": "job_step_result",
    }


def product_cooldown_seconds(operation: str, *, config: Settings = settings) -> int:
    return {
        "profile_update": config.profile_update_cooldown_seconds,
        "username": config.username_cooldown_seconds,
        "profile_photo": config.profile_photo_cooldown_seconds,
        "profile_music": config.profile_music_cooldown_seconds,
        "story_post": config.story_post_cooldown_seconds,
        "story_delete": config.story_delete_cooldown_seconds,
    }.get(operation, 0)


def cooldown_to_dict(row: AccountOperationCooldown) -> dict[str, Any]:
    return {
        "id": row.id,
        "account_id": row.account_id,
        "operation": row.operation,
        "level": row.level,
        "reason_code": row.reason_code,
        "started_at": aware_datetime(row.started_at),
        "retry_after_at": aware_datetime(row.retry_after_at),
        "source": row.source,
        "source_job_id": row.source_job_id,
        "source_step_id": row.source_step_id,
    }


def aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


__all__ = [
    "FLOOD_WAIT_RE",
    "OPERATION_KEYS",
    "STEP_OPERATION_MAP",
    "aware_datetime",
    "cooldown_from_failed_step",
    "cooldown_to_dict",
    "product_cooldown_seconds",
]
