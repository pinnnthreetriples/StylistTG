from __future__ import annotations

from datetime import UTC, datetime, timedelta

from freezegun import freeze_time

from app.models import (
    AccountProxy,
    AccountQuarantine,
    AccountState,
    AccountStatusObservation,
    DEFAULT_LOCAL_USER_ID,
    NeuroCommentEvent,
    WarmupStatus,
    WorkspaceSafetyPolicy,
)
from app.main import app
from app.services.account_status_monitor import (
    AccountStatusMonitor,
    AccountStatusProbeResult,
    STATUS_MONITOR_CHECKPOINT_KEY,
    STATUS_MONITOR_LOCK_KEY,
    run_account_status_monitor_tick,
    _supports_skip_locked,
    is_in_ip_change_cooldown,
)
from app.services.auth_context import AuthContext, get_current_auth_context
from tests.helpers.factories import seed_account
from tests.helpers.warmup import seed_warmup_session, seed_warmup_strategy

_FROZEN_NOW = datetime(2026, 5, 20, 10, 0, tzinfo=UTC)


class _Probe:
    def __init__(self, results: list[AccountStatusProbeResult]) -> None:
        self._results = results

    def check(self, account) -> AccountStatusProbeResult:
        return self._results.pop(0)


class _StateStore:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def set(self, name: str, value: str, *, nx: bool = False, ex: int | None = None):
        if nx and name in self.values:
            return False
        self.values[name] = value
        return True

    def get(self, name: str):
        return self.values.get(name)

    def delete(self, name: str):
        self.values.pop(name, None)
        return 1


def _auth(workspace_id: str) -> AuthContext:
    return AuthContext(
        user_id=DEFAULT_LOCAL_USER_ID,
        workspace_id=workspace_id,
        role="admin",
        auth_source="test",
    )


def _seed_usable_account(db_session, *, host: str = "10.0.0.1", external_ref: str = "+15550102000"):
    account = seed_account(
        db_session,
        external_ref=external_ref,
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    account.proxy = AccountProxy(
        account_id=account.id,
        proxy_type="socks5",
        host=host,
        port=1080,
        status="tcp_working",
    )
    db_session.commit()
    return account


@freeze_time(_FROZEN_NOW)
def test_ip_change_creates_short_cooldown_observation(db_session) -> None:
    account = _seed_usable_account(db_session)
    assert account.terminal_status == "none"
    monitor = AccountStatusMonitor(
        probe=_Probe(
            [
                AccountStatusProbeResult(True, "10.0.0.1", True, "Pixel 7"),
                AccountStatusProbeResult(True, "10.0.0.2", True, "Pixel 7"),
            ]
        )
    )

    monitor.observe_account(db_session, account_id=account.id, workspace_id=account.workspace_id)
    observation = monitor.observe_account(
        db_session, account_id=account.id, workspace_id=account.workspace_id
    )

    actual = {
        "auto_action_taken": observation.auto_action_taken,
        "cooldown": is_in_ip_change_cooldown(
            db_session, account_id=account.id, workspace_id=account.workspace_id
        ),
        "reason": observation.details_json["reason"],
    }
    assert actual == {
        "auto_action_taken": "cooldown",
        "cooldown": True,
        "reason": "ip_change_detected",
    }


@freeze_time(_FROZEN_NOW)
def test_tdlib_ban_errors_mark_account_banned(db_session) -> None:
    account = _seed_usable_account(db_session)
    monitor = AccountStatusMonitor(
        probe=_Probe(
            [
                AccountStatusProbeResult(
                    True,
                    "10.0.0.1",
                    False,
                    "Pixel 7",
                    error_code="USER_DEACTIVATED_BAN",
                    error_class="auth_state",
                ),
            ]
        )
    )

    observation = monitor.observe_account(
        db_session, account_id=account.id, workspace_id=account.workspace_id
    )

    db_session.refresh(account)
    assert {
        "terminal_status": account.terminal_status,
        "auto_action_taken": observation.auto_action_taken,
        "terminal_status_reason": observation.details_json["terminal_status_reason"],
    } == {
        "terminal_status": "banned",
        "auto_action_taken": "paused",
        "terminal_status_reason": "tdlib_auth_error",
    }


@freeze_time(_FROZEN_NOW)
def test_tdlib_user_deactivated_marks_account_deleted(db_session) -> None:
    account = _seed_usable_account(db_session)
    monitor = AccountStatusMonitor(
        probe=_Probe(
            [
                AccountStatusProbeResult(
                    True,
                    "10.0.0.1",
                    False,
                    "Pixel 7",
                    error_code="USER_DEACTIVATED",
                    error_class="auth_state",
                ),
            ]
        )
    )

    monitor.observe_account(db_session, account_id=account.id, workspace_id=account.workspace_id)

    db_session.refresh(account)
    assert account.terminal_status == "deleted"


@freeze_time(_FROZEN_NOW)
def test_auth_class_consecutive_failures_mark_account_banned(db_session) -> None:
    account = _seed_usable_account(db_session)
    monitor = AccountStatusMonitor(
        probe=_Probe(
            [
                AccountStatusProbeResult(
                    True,
                    "10.0.0.1",
                    False,
                    "Pixel 7",
                    error_code="AUTH_KEY_DUPLICATED",
                    error_class="auth_state",
                )
                for _ in range(5)
            ]
        )
    )

    for _ in range(5):
        observation = monitor.observe_account(
            db_session, account_id=account.id, workspace_id=account.workspace_id
        )

    db_session.refresh(account)
    assert {
        "terminal_status": account.terminal_status,
        "consecutive_failures": observation.consecutive_failures,
    } == {
        "terminal_status": "banned",
        "consecutive_failures": 5,
    }


@freeze_time(_FROZEN_NOW)
def test_terminal_status_does_not_auto_revert_after_auth_recovers(db_session) -> None:
    account = _seed_usable_account(db_session)
    account.terminal_status = "banned"
    db_session.commit()
    monitor = AccountStatusMonitor(
        probe=_Probe([AccountStatusProbeResult(True, "10.0.0.1", True, "Pixel 7")])
    )

    monitor.observe_account(db_session, account_id=account.id, workspace_id=account.workspace_id)

    db_session.refresh(account)
    assert account.terminal_status == "banned"


@freeze_time(_FROZEN_NOW)
def test_sticky_ip_violation_opens_status_degraded_quarantine(db_session) -> None:
    account = _seed_usable_account(db_session)
    for index, host in enumerate(("10.0.0.1", "10.0.0.2", "10.0.0.3")):
        db_session.add(
            AccountStatusObservation(
                workspace_id=account.workspace_id,
                account_id=account.id,
                observed_at=_FROZEN_NOW - timedelta(minutes=50 - index),
                proxy_healthy=True,
                proxy_ip_hash=AccountStatusMonitor.hash_proxy_host(host),
                tdlib_authorized=True,
                device_model_hash=AccountStatusMonitor.hash_device_model("Pixel 7"),
                consecutive_failures=0,
                auto_action_taken="none",
                details_json={},
            )
        )
    db_session.commit()

    observation = AccountStatusMonitor(
        probe=_Probe([AccountStatusProbeResult(True, "10.0.0.4", True, "Pixel 7")])
    ).observe_account(db_session, account_id=account.id, workspace_id=account.workspace_id)

    quarantine = db_session.query(AccountQuarantine).one()
    actual = {
        "auto_action_taken": observation.auto_action_taken,
        "reason": quarantine.reason,
        "duration_hours": int((quarantine.until - quarantine.started_at).total_seconds() / 3600),
    }
    assert actual == {
        "auto_action_taken": "quarantine",
        "reason": "status_degraded",
        "duration_hours": 24,
    }


@freeze_time(_FROZEN_NOW)
def test_consecutive_failures_auto_pause_warmup_and_never_auto_resume(db_session) -> None:
    account = _seed_usable_account(db_session)
    strategy = seed_warmup_strategy(db_session)
    warmup = seed_warmup_session(
        db_session,
        account=account,
        strategy=strategy,
        status=WarmupStatus.ACTIVE.value,
        now=_FROZEN_NOW,
    )
    monitor = AccountStatusMonitor(
        probe=_Probe(
            [
                AccountStatusProbeResult(False, "10.0.0.1", True, "Pixel 7"),
                AccountStatusProbeResult(False, "10.0.0.1", True, "Pixel 7"),
                AccountStatusProbeResult(False, "10.0.0.1", True, "Pixel 7"),
                AccountStatusProbeResult(True, "10.0.0.1", True, "Pixel 7"),
            ]
        )
    )

    for _ in range(3):
        monitor.observe_account(
            db_session, account_id=account.id, workspace_id=account.workspace_id
        )
    monitor.observe_account(db_session, account_id=account.id, workspace_id=account.workspace_id)

    db_session.refresh(warmup)
    event = db_session.query(NeuroCommentEvent).one()
    actual = {
        "warmup_status": warmup.status,
        "event_type": event.event_type,
        "event_account_id": event.account_id,
    }
    assert actual == {
        "warmup_status": WarmupStatus.PAUSED_RISK.value,
        "event_type": "account_auto_paused",
        "event_account_id": account.id,
    }


@freeze_time(_FROZEN_NOW)
def test_consecutive_failures_threshold_comes_from_workspace_policy(db_session) -> None:
    account = _seed_usable_account(db_session)
    db_session.add(
        WorkspaceSafetyPolicy(
            workspace_id=account.workspace_id,
            consecutive_failure_threshold=5,
        )
    )
    strategy = seed_warmup_strategy(db_session)
    warmup = seed_warmup_session(
        db_session,
        account=account,
        strategy=strategy,
        status=WarmupStatus.ACTIVE.value,
        now=_FROZEN_NOW,
    )
    monitor = AccountStatusMonitor(
        probe=_Probe(
            [AccountStatusProbeResult(False, "10.0.0.1", True, "Pixel 7") for _ in range(5)]
        )
    )

    for _ in range(4):
        observation = monitor.observe_account(
            db_session, account_id=account.id, workspace_id=account.workspace_id
        )
    db_session.refresh(warmup)
    before_threshold = {
        "warmup_status": warmup.status,
        "consecutive_failures": observation.consecutive_failures,
        "threshold": observation.details_json["threshold"],
    }

    observation = monitor.observe_account(
        db_session, account_id=account.id, workspace_id=account.workspace_id
    )
    db_session.refresh(warmup)
    event = db_session.query(NeuroCommentEvent).one()

    assert before_threshold == {
        "warmup_status": WarmupStatus.ACTIVE.value,
        "consecutive_failures": 4,
        "threshold": 5,
    }
    assert {
        "warmup_status": warmup.status,
        "consecutive_failures": observation.consecutive_failures,
        "event_failures": event.data_json["consecutive_failures"],
        "event_threshold": event.data_json["consecutive_failure_threshold"],
    } == {
        "warmup_status": WarmupStatus.PAUSED_RISK.value,
        "consecutive_failures": 5,
        "event_failures": 5,
        "event_threshold": 5,
    }


@freeze_time(_FROZEN_NOW)
def test_terminal_auth_pause_records_actual_failures_and_policy_threshold(db_session) -> None:
    account = _seed_usable_account(db_session)
    db_session.add(
        WorkspaceSafetyPolicy(
            workspace_id=account.workspace_id,
            consecutive_failure_threshold=20,
        )
    )
    monitor = AccountStatusMonitor(
        probe=_Probe(
            [
                AccountStatusProbeResult(
                    True,
                    "10.0.0.1",
                    False,
                    "Pixel 7",
                    error_code="AUTH_KEY_DUPLICATED",
                    error_class="auth_state",
                )
                for _ in range(5)
            ]
        )
    )

    for _ in range(5):
        monitor.observe_account(
            db_session, account_id=account.id, workspace_id=account.workspace_id
        )

    event = db_session.query(NeuroCommentEvent).one()
    assert event.data_json == {
        "source": "account_status_monitor",
        "consecutive_failures": 5,
        "consecutive_failure_threshold": 20,
        "paused_warmup_session_ids": [],
        "paused_campaign_accounts": 0,
    }


@freeze_time(_FROZEN_NOW)
def test_status_observations_endpoint_is_workspace_scoped(app_client, db_session) -> None:
    account = _seed_usable_account(db_session)
    observation = AccountStatusMonitor(
        probe=_Probe([AccountStatusProbeResult(True, "10.0.0.1", True, "Pixel 7")])
    ).observe_account(db_session, account_id=account.id, workspace_id=account.workspace_id)
    db_session.commit()
    app.dependency_overrides[get_current_auth_context] = lambda: _auth(account.workspace_id)

    response = app_client.get(f"/api/accounts/{account.id}/status-observations?limit=1")

    payload = response.json()
    actual = {
        "status_code": response.status_code,
        "id": payload[0]["id"],
        "account_id": payload[0]["account_id"],
    }
    assert actual == {
        "status_code": 200,
        "id": observation.id,
        "account_id": account.id,
    }


def test_status_monitor_tick_processes_batch_and_sets_checkpoint(db_session) -> None:
    accounts = [
        _seed_usable_account(db_session, external_ref=f"+15550103{index:03d}") for index in range(3)
    ]
    store = _StateStore()
    sorted_ids = sorted(account.id for account in accounts)

    report = run_account_status_monitor_tick(db_session, state_store=store, batch_size=2)

    checkpoint = STATUS_MONITOR_CHECKPOINT_KEY.format(workspace_id=accounts[0].workspace_id)
    assert report.processed_count == 2
    assert len(report.observations) == 2
    assert store.values[checkpoint] == sorted_ids[1]


def test_status_monitor_tick_resumes_from_checkpoint_and_resets_when_exhausted(
    db_session,
) -> None:
    accounts = [
        _seed_usable_account(db_session, external_ref=f"+15550104{index:03d}") for index in range(3)
    ]
    sorted_ids = sorted(account.id for account in accounts)
    store = _StateStore()
    checkpoint = STATUS_MONITOR_CHECKPOINT_KEY.format(workspace_id=accounts[0].workspace_id)
    store.values[checkpoint] = sorted_ids[1]

    resumed = run_account_status_monitor_tick(db_session, state_store=store, batch_size=10)
    exhausted = run_account_status_monitor_tick(db_session, state_store=store, batch_size=10)

    assert resumed.processed_count == 1
    assert store.values.get(checkpoint) is None
    assert exhausted.processed_count == 0


def test_status_monitor_tick_skips_when_lock_is_held(db_session) -> None:
    _seed_usable_account(db_session, external_ref="+15550105000")
    store = _StateStore()
    store.values[STATUS_MONITOR_LOCK_KEY] = "other-tick"

    report = run_account_status_monitor_tick(db_session, state_store=store, batch_size=10)

    assert report.skipped_reason == "another tick in progress"
    assert report.processed_count == 0
    assert db_session.query(AccountStatusObservation).count() == 0


def test_status_monitor_skip_locked_is_postgres_only_for_sqlite_tests(db_session) -> None:
    assert _supports_skip_locked(db_session) is False
