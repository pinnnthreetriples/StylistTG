from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Job, JobState, JobStepResult

PROFILE_SYNC_STALE_AFTER = timedelta(days=7)


def build_reason(
    code: str,
    *,
    severity: str,
    source: str,
    message: str,
    last_seen_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "source": source,
        "message": message,
        "last_seen_at": last_seen_at,
    }


def collect_account_health_signals(session: Session, account: Account) -> dict[str, Any]:
    latest_job = _latest_job(session, account.id)
    latest_failed_step = _latest_failed_step(session, account.id)
    reasons: list[dict[str, Any]] = []

    runtime = account.runtime_state
    profile = account.profile_state
    if runtime is None:
        reasons.append(
            build_reason(
                "runtime_state_missing",
                severity="medium",
                source="runtime",
                message="Нет данных о runtime аккаунта",
            )
        )
    else:
        if runtime.reauth_required or account.account_state == "reauth_required":
            reasons.append(
                build_reason(
                    "reauth_required",
                    severity="blocked",
                    source="runtime",
                    message="Нужна повторная авторизация",
                    last_seen_at=runtime.updated_at,
                )
            )
        if account.account_state in {"runtime_broken", "manual_intervention_needed", "disabled"}:
            reasons.append(
                build_reason(
                    account.account_state,
                    severity="blocked",
                    source="account_state",
                    message="Аккаунт заблокирован текущим состоянием runtime",
                    last_seen_at=account.updated_at,
                )
            )
        if runtime.runtime_health in {"frozen", "session_revoked", "auth_key_unregistered"}:
            reasons.append(
                build_reason(
                    runtime.runtime_health,
                    severity="blocked",
                    source="runtime",
                    message="Сессия или аккаунт требуют ручной проверки",
                    last_seen_at=runtime.updated_at,
                )
            )
        if account.account_state == "execution_usable" and runtime.runtime_health not in {"ready", "unknown"}:
            reasons.append(
                build_reason(
                    "runtime_health_attention",
                    severity="medium",
                    source="runtime",
                    message="Runtime аккаунта требует проверки",
                    last_seen_at=runtime.updated_at,
                )
            )

    if account.account_state != "execution_usable":
        reasons.append(
            build_reason(
                "account_not_execution_usable",
                severity="blocked" if account.account_state in {"reauth_required", "runtime_broken", "manual_intervention_needed", "disabled"} else "medium",
                source="account_state",
                message="Аккаунт сейчас не готов к выполнению задач",
                last_seen_at=account.updated_at,
            )
        )

    if profile is None:
        reasons.append(
            build_reason(
                "profile_sync_unknown",
                severity="medium",
                source="profile_sync",
                message="Профиль ещё не синхронизирован",
            )
        )
    elif profile.synced_at and _aware(profile.synced_at) < datetime.now(UTC) - PROFILE_SYNC_STALE_AFTER:
        reasons.append(
            build_reason(
                "stale_profile_sync",
                severity="medium",
                source="profile_sync",
                message="Профиль давно не синхронизировался",
                last_seen_at=profile.synced_at,
            )
        )

    if latest_job and latest_job.job_state == JobState.PARTIALLY_COMPLETED:
        reasons.append(
            build_reason(
                "recent_partial_job",
                severity="medium",
                source="job",
                message="Недавно задача завершилась частично",
                last_seen_at=latest_job.finished_at or latest_job.started_at or latest_job.queued_at,
            )
        )
    elif latest_job and latest_job.job_state == JobState.FAILED:
        reasons.append(
            build_reason(
                "recent_failed_job",
                severity="medium",
                source="job",
                message="Недавно задача завершилась ошибкой",
                last_seen_at=latest_job.finished_at or latest_job.started_at or latest_job.queued_at,
            )
        )

    if latest_failed_step and latest_failed_step.error_code:
        code = latest_failed_step.error_code
        if "FLOOD_WAIT" in code:
            reasons.append(
                build_reason(
                    "recent_flood_wait",
                    severity="high",
                    source="job_step_result",
                    message="Недавно была ошибка FLOOD_WAIT",
                    last_seen_at=latest_failed_step.finished_at or latest_failed_step.started_at,
                )
            )
        elif latest_failed_step.step_type == "set_username":
            reasons.append(
                build_reason(
                    "username_recently_rejected",
                    severity="medium",
                    source="job_step_result",
                    message="Недавно Telegram отклонил юзернейм",
                    last_seen_at=latest_failed_step.finished_at or latest_failed_step.started_at,
                )
            )
        elif latest_failed_step.step_type in {"post_story_image", "post_story_video"}:
            reasons.append(_story_failure_reason(code, latest_failed_step))

    health_status = _health_status(account, reasons)
    return {
        "health_status": health_status,
        "reasons": reasons,
        "latest_job": latest_job,
        "latest_failed_step": latest_failed_step,
    }


def _story_failure_reason(code: str, step: JobStepResult) -> dict[str, Any]:
    normalized = code.upper()
    if "WEEK" in normalized or "STORY_LIMIT_WEEK" in normalized:
        reason_code = "story_weekly_limit"
        message = "Недавно был достигнут недельный лимит историй"
    elif "ACTIVE" in normalized or "TOO_MANY" in normalized:
        reason_code = "story_active_limit"
        message = "Недавно был достигнут лимит активных историй"
    elif "PREMIUM" in normalized:
        reason_code = "story_premium_required"
        message = "Для недавнего действия с историями требовался Telegram Premium"
    else:
        reason_code = "story_recently_rejected"
        message = "Недавно Telegram отклонил публикацию истории"
    return build_reason(
        reason_code,
        severity="high" if reason_code in {"story_weekly_limit", "story_active_limit"} else "medium",
        source="job_step_result",
        message=message,
        last_seen_at=step.finished_at or step.started_at,
    )


def _health_status(account: Account, reasons: list[dict[str, Any]]) -> str:
    if any(reason["severity"] == "blocked" for reason in reasons):
        return "blocked"
    if account.account_state == "execution_usable" and account.runtime_state and account.runtime_state.runtime_health == "ready":
        if any(reason["severity"] in {"medium", "high"} for reason in reasons):
            return "attention"
        return "ready"
    if reasons:
        return "attention"
    return "unknown"


def _latest_job(session: Session, account_id: str) -> Job | None:
    return session.execute(
        select(Job)
        .where(Job.account_id == account_id)
        .order_by(Job.queued_at.desc(), Job.started_at.desc(), Job.finished_at.desc())
        .limit(1)
    ).scalars().first()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _latest_failed_step(session: Session, account_id: str) -> JobStepResult | None:
    return session.execute(
        select(JobStepResult)
        .join(Job, Job.id == JobStepResult.job_id)
        .where(Job.account_id == account_id)
        .where(JobStepResult.status == "failed")
        .order_by(JobStepResult.finished_at.desc(), JobStepResult.started_at.desc())
        .limit(1)
    ).scalars().first()
