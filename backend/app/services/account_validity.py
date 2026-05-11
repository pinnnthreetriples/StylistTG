from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AccountProfileState,
    AccountState,
    AccountSafetySnapshot,
    AccountValidityCheckRun,
    new_id,
)
from app.services.accounts import get_account
from app.services.account_cooldowns import ensure_cooldowns_from_recent_failures
from app.services.account_safety import build_account_safety, summarize_account_safety
from app.services.operation_logs import log_operation


SUPPORTED_MODES = {"db_snapshot", "tdlib_readonly", "full_capability"}


class ReadOnlyAccountValidityAdapter(Protocol):
    def check_account(self, account_id: str) -> dict[str, Any]:
        """Return read-only account validity data without Telegram write actions."""
        ...


def run_account_validity_check(
    session: Session,
    account_id: str,
    *,
    mode: str = "db_snapshot",
    adapter: ReadOnlyAccountValidityAdapter | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
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

    if mode != "db_snapshot" and adapter is None:
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
        readonly_result: dict[str, Any] | None = None
        if mode != "db_snapshot":
            assert adapter is not None
            readonly_result = adapter.check_account(account_id)
            _apply_readonly_result(session, account_id, readonly_result)
        ensure_cooldowns_from_recent_failures(session, account_id)
        safety = build_account_safety(session, account_id)
        _upsert_safety_snapshot(session, safety)
        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        run.result_json = _json_safe(
            {
                **summarize_account_safety(safety),
                "validity_status": _validity_status_from_readonly_result(readonly_result, safety),
            }
        )
        run.details_json = {"source": mode}
        _rj = run.result_json
        _validity = _rj.get("validity_status") if isinstance(_rj, dict) else None
        log_operation(
            session,
            account_id=account_id,
            operation_type="validity_check",
            operation_key=mode,
            status="completed",
            severity="info",
            source="account_validity",
            message="Account validity check completed",
            workspace_id=workspace_id,
            metadata={"validity_status": _validity},
        )
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
        log_operation(
            session,
            account_id=account_id,
            operation_type="validity_check",
            operation_key=mode,
            status="failed",
            severity="warning",
            source="account_validity",
            message="Account validity check failed",
            error_code="VALIDITY_CHECK_FAILED",
            workspace_id=workspace_id,
            error_class="safety_check",
        )
        session.commit()
        session.refresh(run)
        return validity_check_run_to_dict(run)


def list_account_validity_checks(
    session: Session, account_id: str, *, limit: int = 10
) -> list[dict[str, Any]]:
    runs = (
        session.execute(
            select(AccountValidityCheckRun)
            .where(AccountValidityCheckRun.account_id == account_id)
            .order_by(AccountValidityCheckRun.started_at.desc())
            .limit(max(1, min(limit, 50)))
        )
        .scalars()
        .all()
    )
    return [validity_check_run_to_dict(run) for run in runs]


def latest_account_validity_check(session: Session, account_id: str) -> dict[str, Any] | None:
    run = (
        session.execute(
            select(AccountValidityCheckRun)
            .where(AccountValidityCheckRun.account_id == account_id)
            .order_by(AccountValidityCheckRun.started_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
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
    payload: dict[str, Any] = {
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
        session.add(
            AccountSafetySnapshot(account_id=safety["account_id"], created_at=now, **payload)
        )
        return
    for key, value in payload.items():
        setattr(snapshot, key, value)


def _apply_readonly_result(session: Session, account_id: str, result: dict[str, Any]) -> None:
    account = get_account(session, account_id)
    if account is None:
        raise ValueError("account not found")
    runtime = account.runtime_state
    status = result.get("status")
    if status == "valid":
        account.account_state = AccountState.EXECUTION_USABLE
        if runtime is not None:
            runtime.runtime_health = str(result.get("runtime_health") or "ready")
            runtime.reauth_required = False
            runtime.session_present = True
            runtime.authorized_last_confirmed_at = datetime.now(UTC)
        account.telegram_user_id = result.get("telegram_user_id") or account.telegram_user_id
        raw_profile = result.get("profile")
        profile = cast(dict[str, Any], raw_profile) if isinstance(raw_profile, dict) else {}
        if profile:
            if account.profile_state is None:
                account.profile_state = AccountProfileState(account_id=account.id)
            account.profile_state.telegram_user_id = (
                result.get("telegram_user_id") or account.profile_state.telegram_user_id
            )
            account.profile_state.first_name = profile.get(
                "first_name", account.profile_state.first_name
            )
            account.profile_state.last_name = profile.get(
                "last_name", account.profile_state.last_name
            )
            account.profile_state.username = profile.get("username", account.profile_state.username)
            account.profile_state.bio = profile.get("bio", account.profile_state.bio)
            account.profile_state.synced_at = datetime.now(UTC)
    elif status == "reauth_required":
        account.account_state = AccountState.REAUTH_REQUIRED
        if runtime is not None:
            runtime.runtime_health = "closed"
            runtime.reauth_required = True
    elif status == "runtime_broken":
        account.account_state = AccountState.RUNTIME_BROKEN
        if runtime is not None:
            runtime.runtime_health = "broken"


def _validity_status(safety: dict[str, Any]) -> str:
    codes = {reason["code"] for reason in safety["reasons"]}
    if "reauth_required" in codes:
        return "reauth_required"
    if "runtime_broken" in codes:
        return "runtime_broken"
    if safety["health_status"] == "ready":
        return "valid"
    return "unknown"


def _validity_status_from_readonly_result(
    result: dict[str, Any] | None, safety: dict[str, Any]
) -> str:
    if result and result.get("status"):
        return str(result["status"])
    return _validity_status(safety)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        items = cast(list[object], value)
        return [_json_safe(item) for item in items]
    if isinstance(value, dict):
        items = cast(dict[object, object], value)
        return {key: _json_safe(item) for key, item in items.items()}
    return value
