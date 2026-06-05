from __future__ import annotations

# pyright: reportPrivateUsage=false

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
from typing import Any, Literal, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountState,
    AccountStatusObservation,
    WarmupStatus,
    new_id,
    utc_now,
)
from app.modules.account_survival import events as survival_events
from app.observability.safety_metrics import safety_metrics
from app.modules.account_safety.quarantine import (
    AccountQuarantineService,
    get_active_quarantine,
)
from app.modules.account_safety.policy import (
    get_consecutive_failure_threshold,
    get_workspace_safety_policy,
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


@dataclass(frozen=True)
class AccountStatusProbeResult:
    proxy_healthy: bool
    proxy_host: str | None
    tdlib_authorized: bool
    device_model: str | None
    error_code: str | None = None
    error_class: str | None = None


class AccountStatusProbe(Protocol):
    def check(self, account: Account) -> AccountStatusProbeResult: ...


class StatusMonitorStateStore(Protocol):
    def set(self, name: str, value: str, *, nx: bool = False, ex: int | None = None) -> Any: ...

    def get(self, name: str) -> Any: ...

    def delete(self, name: str) -> Any: ...


@dataclass(frozen=True)
class StatusMonitorReport:
    observations: list[AccountStatusObservation]
    processed_count: int
    skipped_reason: str | None = None


class DatabaseSnapshotStatusProbe:
    """Safe default probe: uses persisted runtime/proxy state, not live TDLib calls."""

    def check(self, account: Account) -> AccountStatusProbeResult:
        proxy = account.proxy
        runtime = account.runtime_state
        return AccountStatusProbeResult(
            proxy_healthy=bool(proxy and proxy.status in _HEALTHY_PROXY_STATUSES),
            proxy_host=proxy.host if proxy is not None else None,
            tdlib_authorized=bool(
                runtime
                and runtime.session_present
                and not runtime.reauth_required
                and account.account_state in _AUTHORIZED_STATES
            ),
            device_model=None,
        )


class AccountStatusMonitor:
    def __init__(self, *, probe: AccountStatusProbe | None = None) -> None:
        self._probe = probe or DatabaseSnapshotStatusProbe()

    @staticmethod
    def hash_proxy_host(host: str | None) -> str | None:
        if not host:
            return None
        return hashlib.sha256(host.strip().lower().encode("utf-8")).hexdigest()

    @staticmethod
    def hash_device_model(device_model: str | None) -> str | None:
        if not device_model:
            return None
        return hashlib.sha256(device_model.strip().lower().encode("utf-8")).hexdigest()

    def tick(
        self,
        session: Session,
        *,
        workspace_id: str | None = None,
        now: datetime | None = None,
    ) -> list[AccountStatusObservation]:
        observations: list[AccountStatusObservation] = []
        for current_workspace_id in _status_monitor_workspace_ids(
            session, workspace_id=workspace_id
        ):
            query = (
                select(Account)
                .where(Account.account_state != AccountState.DISABLED.value)
                .where(Account.workspace_id == current_workspace_id)
                .order_by(Account.updated_at.asc())
            )
            for account in session.execute(query).scalars():
                observations.append(
                    self.observe_account(
                        session,
                        account_id=account.id,
                        workspace_id=account.workspace_id,
                        now=now,
                        account=account,
                    )
                )
        return observations

    def observe_account(
        self,
        session: Session,
        *,
        account_id: str,
        workspace_id: str,
        now: datetime | None = None,
        account: Account | None = None,
    ) -> AccountStatusObservation:
        timestamp = now or utc_now()
        account = account or _get_account(session, account_id=account_id, workspace_id=workspace_id)
        policy = get_workspace_safety_policy(
            session, workspace_id=workspace_id, create_if_missing=True
        )
        if policy is None:
            raise RuntimeError("workspace safety policy was not created")
        consecutive_failure_threshold = get_consecutive_failure_threshold(policy)
        previous = _latest_observation(session, account_id=account_id, workspace_id=workspace_id)
        probe_result = self._probe.check(account)
        proxy_ip_hash = self.hash_proxy_host(probe_result.proxy_host)
        device_model_hash = self.hash_device_model(probe_result.device_model)
        consecutive_failures = _next_consecutive_failures(previous, probe_result)
        details: dict[str, object] = {
            "proxy_host_present": probe_result.proxy_host is not None,
            "threshold": consecutive_failure_threshold,
        }
        if probe_result.error_code:
            details["last_error_code"] = probe_result.error_code
            if "FLOOD_WAIT" in probe_result.error_code.upper():
                safety_metrics.flood_wait(workspace_id=workspace_id, account_id=account_id)
        if probe_result.error_class:
            details["last_error_class"] = probe_result.error_class
        auto_action_taken: AutoAction = "none"

        if _changed(previous.proxy_ip_hash if previous else None, proxy_ip_hash):
            auto_action_taken = "cooldown"
            details.update(
                {
                    "reason": "ip_change_detected",
                    "cooldown_minutes": IP_CHANGE_COOLDOWN_MINUTES,
                    "previous_proxy_ip_hash": previous.proxy_ip_hash if previous else None,
                }
            )

        if _changed(previous.device_model_hash if previous else None, device_model_hash):
            details.update(
                {
                    "device_fingerprint_changed": True,
                    "previous_device_model_hash": previous.device_model_hash if previous else None,
                }
            )

        observation = AccountStatusObservation(
            id=new_id(),
            workspace_id=workspace_id,
            account_id=account_id,
            observed_at=timestamp,
            proxy_healthy=probe_result.proxy_healthy,
            proxy_ip_hash=proxy_ip_hash,
            tdlib_authorized=probe_result.tdlib_authorized,
            device_model_hash=device_model_hash,
            consecutive_failures=consecutive_failures,
            auto_action_taken=auto_action_taken,
            details_json=details,
        )
        session.add(observation)
        session.flush()

        terminal_status = _terminal_status_from_probe(
            probe_result,
            consecutive_failures=consecutive_failures,
        )
        if terminal_status is not None and account.terminal_status == "none":
            account.terminal_status = terminal_status
            survival_events.on_account_terminal(
                session,
                account_id=account_id,
                workspace_id=workspace_id,
                terminal_status=terminal_status,
                now=timestamp,
            )
            _auto_pause_account(
                session,
                account_id=account_id,
                workspace_id=workspace_id,
                now=timestamp,
                consecutive_failures=consecutive_failures,
                consecutive_failure_threshold=consecutive_failure_threshold,
            )
            if observation.auto_action_taken == "none":
                observation.auto_action_taken = "paused"
            observation.details_json = {
                **observation.details_json,
                "terminal_status": terminal_status,
                "terminal_status_reason": "tdlib_auth_error",
                "auto_pause": "terminal_status",
            }

        if (
            _distinct_proxy_hashes_last_hour(
                session,
                account_id=account_id,
                workspace_id=workspace_id,
                now=timestamp,
            )
            > STICKY_IP_MAX_DISTINCT_HASHES
        ):
            if (
                get_active_quarantine(
                    session, account_id=account_id, workspace_id=workspace_id, now=timestamp
                )
                is None
            ):
                AccountQuarantineService(session).open_quarantine(
                    account_id=account_id,
                    workspace_id=workspace_id,
                    reason="status_degraded",
                    duration_hours=24,
                    metadata={"source": "account_status_monitor", "reason": "sticky_ip_violation"},
                )
            observation.auto_action_taken = "quarantine"
            observation.details_json = {**observation.details_json, "reason": "sticky_ip_violation"}

        if _crossed_failure_threshold(
            previous,
            consecutive_failures,
            threshold=consecutive_failure_threshold,
        ):
            _auto_pause_account(
                session,
                account_id=account_id,
                workspace_id=workspace_id,
                now=timestamp,
                consecutive_failures=consecutive_failures,
                consecutive_failure_threshold=consecutive_failure_threshold,
            )
            survival_events.on_account_frozen(
                session,
                account_id=account_id,
                workspace_id=workspace_id,
                now=timestamp,
            )
            if observation.auto_action_taken == "none":
                observation.auto_action_taken = "paused"
            observation.details_json = {
                **observation.details_json,
                "auto_pause": "consecutive_failures",
            }

        session.flush()
        return observation


def is_in_ip_change_cooldown(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    now: datetime | None = None,
) -> bool:
    observation = _latest_observation(session, account_id=account_id, workspace_id=workspace_id)
    if observation is None or observation.auto_action_taken != "cooldown":
        return False
    check_time = now or utc_now()
    return observation.observed_at + timedelta(minutes=IP_CHANGE_COOLDOWN_MINUTES) > check_time


def run_account_status_monitor_tick(
    session: Session,
    *,
    state_store: StatusMonitorStateStore | None = None,
    workspace_id: str | None = None,
    now: datetime | None = None,
    batch_size: int = STATUS_MONITOR_BATCH_SIZE,
) -> StatusMonitorReport:
    lock_acquired = False
    lock_token = new_id()
    if state_store is not None:
        lock_acquired = bool(
            state_store.set(
                STATUS_MONITOR_LOCK_KEY,
                lock_token,
                nx=True,
                ex=STATUS_MONITOR_LOCK_SECONDS,
            )
        )
        if not lock_acquired:
            return StatusMonitorReport(
                observations=[],
                processed_count=0,
                skipped_reason="another tick in progress",
            )

    try:
        monitor = AccountStatusMonitor()
        observations: list[AccountStatusObservation] = []
        for current_workspace_id in _status_monitor_workspace_ids(
            session,
            workspace_id=workspace_id,
        ):
            checkpoint_key = STATUS_MONITOR_CHECKPOINT_KEY.format(workspace_id=current_workspace_id)
            last_account_id = (
                _state_store_text(state_store.get(checkpoint_key)) if state_store else None
            )
            accounts = _status_monitor_accounts(
                session,
                workspace_id=current_workspace_id,
                last_account_id=last_account_id,
                limit=batch_size,
            )
            if not accounts:
                if state_store is not None:
                    state_store.delete(checkpoint_key)
                continue

            for account in accounts:
                observations.append(
                    monitor.observe_account(
                        session,
                        account_id=account.id,
                        workspace_id=account.workspace_id,
                        now=now,
                        account=account,
                    )
                )
            if state_store is not None:
                state_store.set(checkpoint_key, accounts[-1].id)

        return StatusMonitorReport(
            observations=observations,
            processed_count=len(observations),
        )
    finally:
        if state_store is not None and lock_acquired:
            _release_status_monitor_lock(state_store, lock_token)


from app.modules.account_safety.status_monitor_helpers import (  # noqa: E402
    _status_monitor_workspace_ids,
    _status_monitor_accounts,
    _supports_skip_locked as _status_monitor_supports_skip_locked,
    _state_store_text,
    _release_status_monitor_lock,
    _get_account,
    _latest_observation,
    _next_consecutive_failures,
    _changed,
    _distinct_proxy_hashes_last_hour,
    _crossed_failure_threshold,
    _terminal_status_from_probe,
    _auto_pause_account,
)

_supports_skip_locked = _status_monitor_supports_skip_locked
