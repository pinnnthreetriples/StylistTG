from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal, cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountState,
    AccountStatusObservation,
    NeuroCommentCampaign,
    NeuroCommentCampaignAccount,
    NeuroCommentEvent,
    WarmupEvent,
    WarmupSession,
    WarmupStatus,
    new_id,
)

AutoAction = Literal["paused", "quarantine", "cooldown", "none"]
TerminalStatus = Literal["banned", "deleted"]

STATUS_MONITOR_BATCH_SIZE = 500
STATUS_MONITOR_LOCK_KEY = "status_monitor:tick:running"
STATUS_MONITOR_LOCK_SECONDS = 600
STATUS_MONITOR_CHECKPOINT_KEY = "status_monitor:last_checkpoint:{workspace_id}"
IP_CHANGE_COOLDOWN_MINUTES = 30
STICKY_IP_MAX_DISTINCT_HASHES = 3
TERMINAL_AUTH_FAILURE_THRESHOLD = 5
SENSITIVE_WARMUP_EVENT_KEYS = {
    "api_hash",
    "api_key",
    "auth_key",
    "password",
    "proxy_password",
    "session",
    "session_string",
    "tdlib_path",
}

_AUTHORIZED_STATES = {AccountState.AUTHORIZED_READY.value, AccountState.EXECUTION_USABLE.value}
_HEALTHY_PROXY_STATUSES = {"ok", "tcp_working", "tdlib_working"}
_BANNED_TDLIB_ERROR_MARKERS = {"USER_DEACTIVATED_BAN", "AUTH_KEY_UNREGISTERED"}
_DELETED_TDLIB_ERROR_MARKERS = {"USER_DEACTIVATED"}
_AUTH_ERROR_CLASSES = {"AUTH", "AUTH_STATE", "AUTHORIZATION", "TDLIB_AUTH"}
_AUTO_PAUSE_WARMUP_STATUSES = [
    WarmupStatus.VALIDATING.value,
    WarmupStatus.SCHEDULED.value,
    WarmupStatus.ACTIVE.value,
]


from app.modules.account_safety.status_monitor import AccountStatusProbeResult, StatusMonitorStateStore  # noqa: E402

def _status_monitor_workspace_ids(
    session: Session,
    *,
    workspace_id: str | None,
) -> list[str]:
    if workspace_id is not None:
        return [workspace_id]
    return list(
        session.execute(
            select(  # nosemgrep: missing-workspace-id-filter-projection -- Global workspace discovery; account processing is scoped per workspace below.
                Account.workspace_id
            )
            .where(Account.account_state != AccountState.DISABLED.value)
            .distinct()
            .order_by(Account.workspace_id)
        ).scalars()
    )


def _status_monitor_accounts(
    session: Session,
    *,
    workspace_id: str,
    last_account_id: str | None,
    limit: int,
) -> list[Account]:
    stmt = (
        select(Account)
        .where(Account.account_state != AccountState.DISABLED.value)
        .where(Account.workspace_id == workspace_id)
        .order_by(Account.id)
        .limit(limit)
    )
    if last_account_id:
        stmt = stmt.where(Account.id > last_account_id)
    if _supports_skip_locked(session):
        stmt = stmt.with_for_update(skip_locked=True)
    return list(session.execute(stmt).scalars())


def _supports_skip_locked(session: Session) -> bool:
    return session.get_bind().dialect.name == "postgresql"


def _state_store_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _release_status_monitor_lock(state_store: StatusMonitorStateStore, lock_token: str) -> None:
    script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    end
    return 0
    """
    eval_fn = getattr(state_store, "eval", None)
    if callable(eval_fn):
        eval_fn(script, 1, STATUS_MONITOR_LOCK_KEY, lock_token)
        return
    if _state_store_text(state_store.get(STATUS_MONITOR_LOCK_KEY)) == lock_token:
        state_store.delete(STATUS_MONITOR_LOCK_KEY)


def _get_account(session: Session, *, account_id: str, workspace_id: str) -> Account:
    account = session.execute(
        select(Account).where(Account.id == account_id).where(Account.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if account is None:
        raise ValueError("account not found")
    return account


def _latest_observation(
    session: Session, *, account_id: str, workspace_id: str
) -> AccountStatusObservation | None:
    return session.execute(
        select(AccountStatusObservation)
        .where(AccountStatusObservation.workspace_id == workspace_id)
        .where(AccountStatusObservation.account_id == account_id)
        .order_by(AccountStatusObservation.observed_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _next_consecutive_failures(
    previous: AccountStatusObservation | None,
    probe_result: AccountStatusProbeResult,
) -> int:
    if probe_result.proxy_healthy and probe_result.tdlib_authorized:
        return 0
    return (previous.consecutive_failures if previous is not None else 0) + 1


def _changed(previous_hash: str | None, current_hash: str | None) -> bool:
    return bool(previous_hash and current_hash and previous_hash != current_hash)


def _distinct_proxy_hashes_last_hour(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    now: datetime,
) -> int:
    return int(
        session.execute(
            select(func.count(func.distinct(AccountStatusObservation.proxy_ip_hash)))
            .where(AccountStatusObservation.workspace_id == workspace_id)
            .where(AccountStatusObservation.account_id == account_id)
            .where(AccountStatusObservation.observed_at >= now - timedelta(minutes=60))
            .where(AccountStatusObservation.proxy_ip_hash.is_not(None))
        ).scalar_one()
        or 0
    )


def _crossed_failure_threshold(
    previous: AccountStatusObservation | None,
    consecutive_failures: int,
    *,
    threshold: int,
) -> bool:
    previous_failures = previous.consecutive_failures if previous is not None else 0
    return previous_failures < threshold and consecutive_failures >= threshold


def _terminal_status_from_probe(
    probe_result: AccountStatusProbeResult,
    *,
    consecutive_failures: int,
) -> TerminalStatus | None:
    error_code = _normalize_error_token(probe_result.error_code)
    if any(marker in error_code for marker in _BANNED_TDLIB_ERROR_MARKERS):
        return "banned"
    if any(marker in error_code for marker in _DELETED_TDLIB_ERROR_MARKERS):
        return "deleted"
    if consecutive_failures >= TERMINAL_AUTH_FAILURE_THRESHOLD and _is_auth_class_error(
        probe_result
    ):
        return "banned"
    return None


def _is_auth_class_error(probe_result: AccountStatusProbeResult) -> bool:
    error_class = _normalize_error_token(probe_result.error_class)
    if error_class in _AUTH_ERROR_CLASSES or "AUTH" in error_class:
        return True
    error_code = _normalize_error_token(probe_result.error_code)
    return "AUTH" in error_code


def _normalize_error_token(value: str | None) -> str:
    return (value or "").strip().upper()


def _auto_pause_account(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    now: datetime,
    consecutive_failures: int,
    consecutive_failure_threshold: int,
) -> None:
    paused_warmups: list[str] = []
    warmups = session.execute(
        select(WarmupSession)
        .where(WarmupSession.workspace_id == workspace_id)
        .where(WarmupSession.account_id == account_id)
        .where(WarmupSession.status.in_(_AUTO_PAUSE_WARMUP_STATUSES))
    ).scalars()
    for warmup_session in warmups:
        warmup_session.status = WarmupStatus.PAUSED_RISK.value
        warmup_session.paused_at = now
        warmup_session.updated_at = now
        warmup_session.next_micro_session_at = None
        warmup_session.next_step_at = None
        _write_warmup_event(
            session,
            warmup_session,
            "paused_risk",
            {"reason": "account_status_monitor_consecutive_failures"},
        )
        paused_warmups.append(warmup_session.id)

    paused_campaign_accounts = 0
    campaign_accounts = session.execute(
        select(NeuroCommentCampaignAccount)
        .join(NeuroCommentCampaign)
        .where(NeuroCommentCampaign.workspace_id == workspace_id)
        .where(NeuroCommentCampaignAccount.account_id == account_id)
        .where(NeuroCommentCampaignAccount.status == "active")
    ).scalars()
    for campaign_account in campaign_accounts:
        campaign_account.status = "paused"
        paused_campaign_accounts += 1

    session.add(
        NeuroCommentEvent(
            id=new_id(),
            workspace_id=workspace_id,
            account_id=account_id,
            event_type="account_auto_paused",
            event_level="warning",
            message="Account auto-paused after repeated status monitor failures",
            data_json={
                "source": "account_status_monitor",
                "consecutive_failures": consecutive_failures,
                "consecutive_failure_threshold": consecutive_failure_threshold,
                "paused_warmup_session_ids": paused_warmups,
                "paused_campaign_accounts": paused_campaign_accounts,
            },
            created_at=now,
        )
    )


def _write_warmup_event(
    session: Session,
    warmup_session: WarmupSession,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> WarmupEvent:
    event = WarmupEvent(
        id=new_id(),
        workspace_id=warmup_session.workspace_id,
        session_id=warmup_session.id,
        event_type=event_type,
        payload_json=_sanitize_warmup_event_payload(payload or {}),
    )
    session.add(event)
    return event


def _sanitize_warmup_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in SENSITIVE_WARMUP_EVENT_KEYS:
            sanitized[key] = "[redacted]"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_warmup_event_payload(cast(dict[str, Any], value))
        elif isinstance(value, list):
            items = cast(list[object], value)
            sanitized[key] = [
                _sanitize_warmup_event_payload(cast(dict[str, Any], item))
                if isinstance(item, dict)
                else item
                for item in items
            ]
        else:
            sanitized[key] = value
    return sanitized
