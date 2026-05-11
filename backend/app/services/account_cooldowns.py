from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.models import AccountOperationCooldown, Job, JobStepResult, StepStatus

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


def ensure_cooldowns_from_recent_failures(
    session: Session,
    account_id: str,
    *,
    config: Settings = settings,
) -> None:
    for step in _recent_failed_steps(session, account_id):
        cooldown = cooldown_from_failed_step(step, config=config)
        if cooldown is None:
            continue
        _upsert_cooldown(session, account_id, step, cooldown)
    session.flush()


def recent_failure_cooldowns_by_operation(
    session: Session,
    account_id: str,
    *,
    config: Settings = settings,
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {operation: [] for operation in OPERATION_KEYS}
    steps = _recent_failed_steps(session, account_id)
    for step in steps:
        cooldown = cooldown_from_failed_step(step, config=config)
        if cooldown is None:
            continue
        result.setdefault(cooldown["operation"], []).append(
            {
                "id": f"recent:{step.id}",
                "account_id": account_id,
                "operation": cooldown["operation"],
                "level": cooldown["level"],
                "reason_code": cooldown["reason_code"],
                "started_at": cooldown["started_at"],
                "retry_after_at": cooldown["retry_after_at"],
                "source": cooldown["source"],
                "source_job_id": step.job_id,
                "source_step_id": step.id,
            }
        )
    return result


def active_cooldowns_by_operation(
    session: Session, account_id: str, *, now: datetime | None = None
) -> dict[str, list[dict[str, Any]]]:
    now = now or datetime.now(UTC)
    rows = (
        session.execute(
            select(AccountOperationCooldown)
            .where(AccountOperationCooldown.account_id == account_id)
            .where(AccountOperationCooldown.retry_after_at > now)
            .order_by(AccountOperationCooldown.retry_after_at.desc())
        )
        .scalars()
        .all()
    )
    result: dict[str, list[dict[str, Any]]] = {operation: [] for operation in OPERATION_KEYS}
    for row in rows:
        result.setdefault(row.operation, []).append(cooldown_to_dict(row))
    return result


def list_active_account_cooldowns(
    session: Session, account_id: str, *, now: datetime | None = None
) -> list[dict[str, Any]]:
    now = now or datetime.now(UTC)
    rows = (
        session.execute(
            select(AccountOperationCooldown)
            .where(AccountOperationCooldown.account_id == account_id)
            .where(AccountOperationCooldown.retry_after_at > now)
            .order_by(AccountOperationCooldown.retry_after_at.desc())
        )
        .scalars()
        .all()
    )
    return [cooldown_to_dict(row) for row in rows]


def create_cooldown_from_error(
    session: Session,
    *,
    account_id: str,
    operation: str,
    error_code: str,
    source_job_id: str | None = None,
    now: datetime | None = None,
) -> AccountOperationCooldown | None:
    now = now or datetime.now(UTC)
    match = FLOOD_WAIT_RE.search(error_code)
    if not match:
        return None
    seconds = min(max(int(match.group("seconds")), 1), 7 * 24 * 3600)
    row = AccountOperationCooldown(
        account_id=account_id,
        operation=operation,
        level="blocked",
        reason_code="recent_flood_wait",
        started_at=now,
        retry_after_at=now + timedelta(seconds=seconds),
        source="execution_error",
        source_job_id=source_job_id,
    )
    session.add(row)
    session.flush()
    return row


def product_cooldowns_by_operation(
    session: Session,
    account_id: str,
    *,
    config: Settings = settings,
    now: datetime | None = None,
) -> dict[str, list[dict[str, Any]]]:
    now = now or datetime.now(UTC)
    result: dict[str, list[dict[str, Any]]] = {operation: [] for operation in OPERATION_KEYS}
    for step_type, operation in STEP_OPERATION_MAP.items():
        seconds = product_cooldown_seconds(operation, config=config)
        if seconds <= 0:
            continue
        step = _latest_succeeded_step(session, account_id, step_type)
        if step is None:
            continue
        finished_at = step.finished_at or step.started_at
        if finished_at is None:
            continue
        retry_after = _aware(finished_at) + timedelta(seconds=seconds)
        if retry_after <= now:
            continue
        result.setdefault(operation, []).append(
            {
                "id": f"product:{step.id}",
                "account_id": account_id,
                "operation": operation,
                "level": "warning",
                "reason_code": f"product_cooldown:{operation}",
                "started_at": finished_at,
                "retry_after_at": retry_after,
                "source": "product_policy",
                "source_job_id": step.job_id,
                "source_step_id": step.id,
            }
        )
    return result


def merge_cooldowns(*groups: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {operation: [] for operation in OPERATION_KEYS}
    for group in groups:
        for operation, cooldowns in group.items():
            result.setdefault(operation, []).extend(cooldowns)
    return result


def cooldown_from_failed_step(
    step: JobStepResult, *, config: Settings = settings
) -> dict[str, Any] | None:
    error_code = step.error_code or ""
    match = FLOOD_WAIT_RE.search(error_code)
    operation = STEP_OPERATION_MAP.get(step.step_type, "profile_update")
    started_at = step.finished_at or step.started_at or datetime.now(UTC)
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
            "retry_after_at": _aware(started_at) + timedelta(seconds=seconds),
            "source": "job_step_result",
        }
    return {
        "operation": operation,
        "level": "blocked",
        "reason_code": "recent_flood_wait",
        "started_at": started_at,
        "retry_after_at": _aware(started_at) + timedelta(seconds=int(match.group("seconds"))),
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
        "started_at": _aware(row.started_at),
        "retry_after_at": _aware(row.retry_after_at),
        "source": row.source,
        "source_job_id": row.source_job_id,
        "source_step_id": row.source_step_id,
    }


def _upsert_cooldown(
    session: Session,
    account_id: str,
    step: JobStepResult,
    cooldown: dict[str, Any],
) -> None:
    existing = (
        session.execute(
            select(AccountOperationCooldown)
            .where(AccountOperationCooldown.account_id == account_id)
            .where(AccountOperationCooldown.source_step_id == step.id)
            .limit(1)
        )
        .scalars()
        .first()
    )
    payload: dict[str, Any] = {
        "operation": cooldown["operation"],
        "level": cooldown["level"],
        "reason_code": cooldown["reason_code"],
        "started_at": cooldown["started_at"],
        "retry_after_at": cooldown["retry_after_at"],
        "source": cooldown["source"],
        "source_job_id": step.job_id,
        "source_step_id": step.id,
    }
    if existing is None:
        session.add(AccountOperationCooldown(account_id=account_id, **payload))
        return
    for key, value in payload.items():
        setattr(existing, key, value)


def batch_active_cooldowns_by_operation(
    session: Session,
    account_ids: list[str],
    *,
    now: datetime | None = None,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Return {account_id: {operation: [cooldowns]}} for all accounts in one query."""
    now = now or datetime.now(UTC)
    if not account_ids:
        return {}
    rows = (
        session.execute(
            select(AccountOperationCooldown)
            .where(AccountOperationCooldown.account_id.in_(account_ids))
            .where(AccountOperationCooldown.retry_after_at > now)
            .order_by(AccountOperationCooldown.retry_after_at.desc())
        )
        .scalars()
        .all()
    )
    result: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in rows:
        per_account = result.setdefault(row.account_id, {op: [] for op in OPERATION_KEYS})
        per_account.setdefault(row.operation, []).append(cooldown_to_dict(row))
    return result


def batch_recent_failed_steps(
    session: Session,
    account_ids: list[str],
) -> dict[str, list[JobStepResult]]:
    """Return {account_id: [steps]} for all accounts in one query."""
    if not account_ids:
        return {}
    rows = session.execute(
        select(Job.account_id, JobStepResult)
        .join(Job, Job.id == JobStepResult.job_id)
        .where(Job.account_id.in_(account_ids))
        .where(JobStepResult.status == StepStatus.FAILED)
        .where(JobStepResult.error_code.is_not(None))
        .order_by(Job.account_id, JobStepResult.finished_at.desc(), JobStepResult.started_at.desc())
    ).all()
    result: dict[str, list[JobStepResult]] = {}
    for account_id, step in rows:
        steps = result.setdefault(account_id, [])
        if len(steps) < 20:
            steps.append(step)
    return result


def batch_latest_succeeded_steps(
    session: Session,
    account_ids: list[str],
) -> dict[tuple[str, str], JobStepResult]:
    """Return {(account_id, step_type): step} for latest succeeded steps of all step types."""
    if not account_ids:
        return {}
    step_types = list(STEP_OPERATION_MAP.keys())
    rows = session.execute(
        select(Job.account_id, JobStepResult)
        .join(Job, Job.id == JobStepResult.job_id)
        .where(Job.account_id.in_(account_ids))
        .where(JobStepResult.step_type.in_(step_types))
        .where(JobStepResult.status == StepStatus.SUCCEEDED)
        .order_by(
            Job.account_id,
            JobStepResult.step_type,
            JobStepResult.finished_at.desc(),
            JobStepResult.started_at.desc(),
        )
    ).all()
    result: dict[tuple[str, str], JobStepResult] = {}
    for account_id, step in rows:
        key = (account_id, step.step_type)
        if key not in result:
            result[key] = step
    return result


def recent_failure_cooldowns_from_steps(
    steps: list[JobStepResult],
    account_id: str,
    *,
    config: Settings = settings,
) -> dict[str, list[dict[str, Any]]]:
    """Compute recent failure cooldowns from pre-fetched steps (no DB calls)."""
    result: dict[str, list[dict[str, Any]]] = {operation: [] for operation in OPERATION_KEYS}
    for step in steps:
        cooldown = cooldown_from_failed_step(step, config=config)
        if cooldown is None:
            continue
        result.setdefault(cooldown["operation"], []).append(
            {
                "id": f"recent:{step.id}",
                "account_id": account_id,
                "operation": cooldown["operation"],
                "level": cooldown["level"],
                "reason_code": cooldown["reason_code"],
                "started_at": cooldown["started_at"],
                "retry_after_at": cooldown["retry_after_at"],
                "source": cooldown["source"],
                "source_job_id": step.job_id,
                "source_step_id": step.id,
            }
        )
    return result


def product_cooldowns_from_steps(
    succeeded_steps: dict[tuple[str, str], JobStepResult],
    account_id: str,
    *,
    config: Settings = settings,
    now: datetime | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Compute product cooldowns from pre-fetched succeeded steps (no DB calls)."""
    now = now or datetime.now(UTC)
    result: dict[str, list[dict[str, Any]]] = {operation: [] for operation in OPERATION_KEYS}
    for step_type, operation in STEP_OPERATION_MAP.items():
        seconds = product_cooldown_seconds(operation, config=config)
        if seconds <= 0:
            continue
        step = succeeded_steps.get((account_id, step_type))
        if step is None:
            continue
        finished_at = step.finished_at or step.started_at
        if finished_at is None:
            continue
        retry_after = _aware(finished_at) + timedelta(seconds=seconds)
        if retry_after <= now:
            continue
        result.setdefault(operation, []).append(
            {
                "id": f"product:{step.id}",
                "account_id": account_id,
                "operation": operation,
                "level": "warning",
                "reason_code": f"product_cooldown:{operation}",
                "started_at": finished_at,
                "retry_after_at": retry_after,
                "source": "product_policy",
                "source_job_id": step.job_id,
                "source_step_id": step.id,
            }
        )
    return result


def _recent_failed_steps(session: Session, account_id: str) -> list[JobStepResult]:
    return list(
        session.execute(
            select(JobStepResult)
            .join(Job, Job.id == JobStepResult.job_id)
            .where(Job.account_id == account_id)
            .where(JobStepResult.status == StepStatus.FAILED)
            .where(JobStepResult.error_code.is_not(None))
            .order_by(JobStepResult.finished_at.desc(), JobStepResult.started_at.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )


def _latest_succeeded_step(
    session: Session, account_id: str, step_type: str
) -> JobStepResult | None:
    return (
        session.execute(
            select(JobStepResult)
            .join(Job, Job.id == JobStepResult.job_id)
            .where(Job.account_id == account_id)
            .where(JobStepResult.step_type == step_type)
            .where(JobStepResult.status == StepStatus.SUCCEEDED)
            .order_by(JobStepResult.finished_at.desc(), JobStepResult.started_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
