from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AccountSafetySnapshot,
    AccountValidityCheckRun,
    new_id,
)
from app.services.accounts import get_account
from app.services.account_safety import build_account_safety, summarize_account_safety


SUPPORTED_MODES = {"db_snapshot", "tdlib_readonly", "full_capability"}


def run_account_validity_check(session: Session, account_id: str, *, mode: str = "db_snapshot") -> dict[str, Any]:
    if mode not in SUPPORTED_MODES:
        raise ValueError("unsupported validity check mode")
    if get_account(session, account_id) is None:
        raise ValueError("account not found")

    started_at = datetime.now(UTC)
    run = AccountValidityCheckRun(
        id=new_id(),
        account_id=account_id,
        mode=mode,
        status="running",
        started_at=started_at,
        created_at=started_at,
    )
    session.add(run)

    if mode != "db_snapshot":
        run.status = "unsupported"
        run.finished_at = datetime.now(UTC)
        run.error_code = "TDLIB_READONLY_CHECK_NOT_ENABLED"
        run.error_class = "safety_check"
        run.details_json = {
            "reason": "live_tdlib_readonly_check_requires_explicit_enablement",
            "safe": True,
        }
        session.commit()
        session.refresh(run)
        return validity_check_run_to_dict(run)

    try:
        safety = build_account_safety(session, account_id)
        _upsert_safety_snapshot(session, safety)
        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        run.result_json = _json_safe(summarize_account_safety(safety))
        run.details_json = {"source": "db_snapshot"}
        session.commit()
        session.refresh(run)
        return validity_check_run_to_dict(run)
    except ValueError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        failed_at = datetime.now(UTC)
        run = AccountValidityCheckRun(
            id=run.id,
            account_id=account_id,
            mode=mode,
            status="failed",
            started_at=started_at,
            finished_at=failed_at,
            error_code="VALIDITY_CHECK_FAILED",
            error_class="safety_check",
            created_at=started_at,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return validity_check_run_to_dict(run)


def list_account_validity_checks(session: Session, account_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
    runs = session.execute(
        select(AccountValidityCheckRun)
        .where(AccountValidityCheckRun.account_id == account_id)
        .order_by(AccountValidityCheckRun.started_at.desc())
        .limit(max(1, min(limit, 50)))
    ).scalars().all()
    return [validity_check_run_to_dict(run) for run in runs]


def latest_account_validity_check(session: Session, account_id: str) -> dict[str, Any] | None:
    run = session.execute(
        select(AccountValidityCheckRun)
        .where(AccountValidityCheckRun.account_id == account_id)
        .order_by(AccountValidityCheckRun.started_at.desc())
        .limit(1)
    ).scalars().first()
    return validity_check_run_to_dict(run) if run else None


def validity_check_run_to_dict(run: AccountValidityCheckRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "account_id": run.account_id,
        "mode": run.mode,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "error_code": run.error_code,
        "error_class": run.error_class,
        "details": run.details_json,
        "result": run.result_json,
        "created_at": run.created_at,
    }


def _upsert_safety_snapshot(session: Session, safety: dict[str, Any]) -> None:
    snapshot = session.get(AccountSafetySnapshot, safety["account_id"])
    now = datetime.now(UTC)
    payload = {
        "health_status": safety["health_status"],
        "overall_risk_level": safety["overall_risk_level"],
        "validity_status": safety["validity_status"],
        "capabilities_json": _json_safe(safety["capabilities"]),
        "risk_by_operation_json": _json_safe(safety["risk_by_operation"]),
        "reasons_json": _json_safe(safety["reasons"]),
        "signals_json": _json_safe({"top_reasons": safety["top_reasons"]}),
        "last_checked_at": safety["last_checked_at"],
        "source": safety["source"],
        "updated_at": now,
    }
    if snapshot is None:
        session.add(AccountSafetySnapshot(account_id=safety["account_id"], created_at=now, **payload))
        return
    for key, value in payload.items():
        setattr(snapshot, key, value)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value
