from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from redis.exceptions import RedisError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Job, JobStepResult
from app.services.accounts import get_account
from app.services.redis_client import redis_from_url


def build_runtime_diagnostics() -> dict[str, Any]:
    diagnostics = {
        "database": "down",
        "redis": "down",
        "tdlib": "configured" if _tdlib_credentials_present() else "not_configured",
    }
    try:
        with SessionLocal() as session:
            session.execute(text("select 1"))
        diagnostics["database"] = "ok"
    except Exception:
        diagnostics["database"] = "down"

    try:
        redis = redis_from_url(socket_connect_timeout=1, socket_timeout=1)
        cast(Any, redis).ping()
        diagnostics["redis"] = "ok"
    except RedisError:
        diagnostics["redis"] = "down"
    except Exception:
        diagnostics["redis"] = "down"
    return diagnostics


def account_runtime_diagnostics(session: Session, account_id: str) -> dict[str, Any]:
    account = get_account(session, account_id)
    if account is None:
        raise ValueError("account not found")
    latest_step = _latest_step_result_for_account(session, account_id)
    return {
        "account_id": account.id,
        "account_state": account.account_state,
        "runtime_health": account.runtime_state.runtime_health,
        "reauth_required": account.runtime_state.reauth_required,
        "authorized_last_confirmed_at": account.runtime_state.authorized_last_confirmed_at,
        "can_start_profile_job": account.account_state == "execution_usable",
        "last_error_code": latest_step.error_code if latest_step else None,
        "last_error_class": latest_step.error_class if latest_step else None,
        "tdlib_configured": _tdlib_credentials_present(),
        "manual_intervention_required": account.runtime_state.runtime_health
        == "manual_intervention_needed"
        or account.account_state == "manual_intervention_needed",
        "recovery_marker": account.runtime_state.recovery_marker,
        "lock_owner": account.runtime_state.lock_owner,
        "lock_epoch": account.runtime_state.lock_epoch,
        "diagnostic_timestamp": datetime.now(UTC).isoformat(),
    }


def _latest_step_result_for_account(session: Session, account_id: str) -> JobStepResult | None:
    statement = (
        select(JobStepResult)
        .join(Job, Job.id == JobStepResult.job_id)
        .where(Job.account_id == account_id)
        .order_by(JobStepResult.finished_at.desc(), JobStepResult.started_at.desc())
    )
    return session.execute(statement).scalars().first()


def _tdlib_credentials_present() -> bool:
    return bool(settings.tdlib_api_id and settings.tdlib_api_hash)
