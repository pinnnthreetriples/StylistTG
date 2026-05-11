"""Phase 1: pytest для shadow-execution dispatch-движка.

Note: SQLite не сохраняет tz, поэтому все сравнения datetime идут через
`_as_utc` (см. test_warmup_worker.py). CHECK constraint
`ck_warmup_strategy_duration_days` ограничивает duration_days диапазоном
3..30, поэтому тесты на быстрое завершение делают несколько dispatch-итераций.


Контракты:
- Dispatch ходит только по сессиям с execution_mode != dry_run.
- Симулирует действия из daily_action_limits, инкрементируя daily_counters.
- Уважает quiet hours и переносит next_micro_session_at на конец quiet-окна.
- Когда лимиты дня исчерпаны — двигает current_day и пишет day_advanced.
- Когда current_day достигает duration_days — завершает сессию и снимает
  isolation claim.
- create_warmup_session для shadow/passive/network/advanced берёт claim,
  для dry_run — не берёт.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.models import (
    AccountProxy,
    AccountRuntimeState,
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    ProxyCategory,
    WarmupExecutionMode,
    WarmupIsolationClaim,
    WarmupPresetKind,
    WarmupSession,
    WarmupStatus,
    WarmupStrategy,
    new_id,
)
from app.services.accounts import create_account
from app.services.warmup import create_warmup_session
from app.services.warmup_dispatch import process_due_warmup_dispatches
from app.services.warmup_isolation import get_claim
from app.services.warmup_worker import process_due_warmup_sessions


def _seed_account(db_session, *, with_proxy: bool = True):
    account = create_account(
        db_session,
        external_ref=f"+7999{new_id()[:8]}",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state = AccountRuntimeState(
        account_id=account.id,
        session_present=True,
        runtime_health="ready",
        reauth_required=False,
    )
    if with_proxy:
        account.proxy = AccountProxy(
            account_id=account.id,
            proxy_type="socks5",
            proxy_category=ProxyCategory.RESIDENTIAL.value,
            host="127.0.0.1",
            port=1080,
            username="user",
            password_encrypted=None,
            status="ok",
        )
    db_session.commit()
    return account


def _seed_shadow_strategy(
    db_session,
    *,
    duration_days: int = 3,
    daily_action_limits: dict | None = None,
) -> WarmupStrategy:
    strategy = WarmupStrategy(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        name=f"Shadow {new_id()[:6]}",
        description="Shadow test",
        tier_limits_json={"cadence_hours": 24, "profile_required": True},
        target_channels_json=[],
        is_preset=False,
        execution_mode=WarmupExecutionMode.SHADOW.value,
        preset_kind=WarmupPresetKind.STANDARD.value,
        duration_days=duration_days,
        daily_action_limits_json=daily_action_limits
        or {
            "1": {"feed_read": 2, "join_chat": 0, "p2p_send": 0},
            "2": {"feed_read": 2, "join_chat": 1, "p2p_send": 0},
            "3": {"feed_read": 2, "join_chat": 1, "p2p_send": 1},
        },
        session_window_config_json={"micro_sessions_per_day": {"min": 3, "max": 6}},
        ui_summary_json={"audience_hint": "Shadow"},
    )
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _seed_dry_run_strategy(db_session) -> WarmupStrategy:
    strategy = WarmupStrategy(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        name=f"DryRun {new_id()[:6]}",
        description="DryRun test",
        tier_limits_json={"cadence_hours": 24, "profile_required": True},
        target_channels_json=[],
        is_preset=True,
        execution_mode=WarmupExecutionMode.DRY_RUN.value,
        duration_days=14,
    )
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _seeded_session(db_session, *, strategy: WarmupStrategy) -> WarmupSession:
    account = _seed_account(db_session)
    return create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        now=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )


def test_create_warmup_session_acquires_claim_for_shadow(db_session) -> None:
    strategy = _seed_shadow_strategy(db_session)
    warmup_session = _seeded_session(db_session, strategy=strategy)

    claim = db_session.get(WarmupIsolationClaim, warmup_session.account_id)
    assert claim is not None
    assert claim.held_by == f"warmup:{warmup_session.id}"
    assert warmup_session.next_micro_session_at is not None


def test_create_warmup_session_does_not_claim_for_dry_run(db_session) -> None:
    strategy = _seed_dry_run_strategy(db_session)
    warmup_session = _seeded_session(db_session, strategy=strategy)

    assert get_claim(db_session, account_id=warmup_session.account_id) is None
    assert warmup_session.next_micro_session_at is None


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def test_dispatch_simulates_actions_and_increments_counters(db_session) -> None:
    strategy = _seed_shadow_strategy(db_session)
    warmup_session = _seeded_session(db_session, strategy=strategy)
    # Force determinism: action selection drops based on rng.random()
    rng = random.Random(0)
    when = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)

    processed = process_due_warmup_dispatches(db_session, worker_id="worker-1", now=when, rng=rng)

    assert processed == 1
    db_session.refresh(warmup_session)
    counters = warmup_session.daily_counters_json["0"]
    # day index 0 maps to plan key "1" (1-indexed) → feed_read budget=2
    assert counters.get("feed_read", 0) >= 1
    assert _as_utc(warmup_session.last_micro_session_at) == when
    assert warmup_session.next_micro_session_at is not None
    assert _as_utc(warmup_session.next_micro_session_at) > when
    events = sorted(warmup_session.events, key=lambda e: e.created_at)
    event_types = [event.event_type for event in events]
    assert "isolation_claimed" in event_types
    assert "micro_session_window_opened" in event_types
    assert "session_action_simulated" in event_types
    assert "micro_session_window_closed" in event_types


def test_dispatch_skips_dry_run_sessions(db_session) -> None:
    strategy = _seed_dry_run_strategy(db_session)
    warmup_session = _seeded_session(db_session, strategy=strategy)
    # ensure next_micro_session_at is None for dry_run
    assert warmup_session.next_micro_session_at is None

    processed = process_due_warmup_dispatches(
        db_session, worker_id="worker-1", now=datetime(2026, 6, 1, 12, tzinfo=UTC)
    )
    assert processed == 0


def test_shadow_dispatch_runs_when_live_warmup_is_disabled(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "warmup_live_enabled", False)
    strategy = _seed_shadow_strategy(db_session, daily_action_limits={"1": {"feed_read": 1}})
    warmup_session = _seeded_session(db_session, strategy=strategy)

    processed = process_due_warmup_dispatches(
        db_session,
        worker_id="worker-1",
        now=datetime(2026, 6, 1, 12, tzinfo=UTC),
        rng=random.Random(0),
    )

    assert processed == 1
    db_session.refresh(warmup_session)
    assert warmup_session.daily_counters_json.get("0", {}).get("feed_read") == 1


def test_dry_run_worker_skips_shadow_sessions(db_session) -> None:
    strategy = _seed_shadow_strategy(db_session)
    _seeded_session(db_session, strategy=strategy)

    processed = process_due_warmup_sessions(
        db_session, worker_id="worker-dry", now=datetime(2026, 6, 1, 12, tzinfo=UTC)
    )
    assert processed == 0


def _force_due_now(db_session, warmup_session: WarmupSession, when: datetime) -> None:
    """Helper: bring next_micro_session_at to `when` between dispatch ticks."""
    warmup_session.next_micro_session_at = when
    db_session.commit()


def test_dispatch_advances_day_when_daily_caps_exhausted(db_session) -> None:
    # minimal plan: 1 action per day for the full duration_days=3 (CHECK >= 3)
    strategy = _seed_shadow_strategy(
        db_session,
        duration_days=3,
        daily_action_limits={
            "1": {"feed_read": 1},
            "2": {"join_chat": 1},
            "3": {"p2p_send": 1},
        },
    )
    warmup_session = _seeded_session(db_session, strategy=strategy)
    rng = random.Random(1)
    when = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)

    process_due_warmup_dispatches(db_session, worker_id="worker-1", now=when, rng=rng)

    db_session.refresh(warmup_session)
    assert warmup_session.current_day == 1, "day advanced when daily cap hit"
    assert warmup_session.daily_counters_json.get("0", {}).get("feed_read") == 1


def test_dispatch_completes_session_at_duration_end(db_session) -> None:
    strategy = _seed_shadow_strategy(
        db_session,
        duration_days=3,
        daily_action_limits={
            "1": {"feed_read": 1},
            "2": {"feed_read": 1},
            "3": {"feed_read": 1},
        },
    )
    warmup_session = _seeded_session(db_session, strategy=strategy)
    rng = random.Random(0)
    when = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)

    # In production a micro-session occasionally drops an action via jitter,
    # so day completion may take more than one tick per day. Loop until the
    # session is COMPLETED or we hit a generous safety bound.
    for _ in range(30):
        process_due_warmup_dispatches(db_session, worker_id="worker-1", now=when, rng=rng)
        db_session.refresh(warmup_session)
        if warmup_session.status == WarmupStatus.COMPLETED.value:
            break
        _force_due_now(db_session, warmup_session, when)

    assert warmup_session.status == WarmupStatus.COMPLETED.value
    assert _as_utc(warmup_session.completed_at) == when
    # claim must be released on completion
    assert get_claim(db_session, account_id=warmup_session.account_id) is None
    event_types = {event.event_type for event in warmup_session.events}
    assert "completed" in event_types
    assert "isolation_released" in event_types


def test_dispatch_respects_quiet_hours(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "warmup_quiet_hours_local_start", 23)
    monkeypatch.setattr(settings, "warmup_quiet_hours_local_end", 8)
    strategy = _seed_shadow_strategy(db_session)
    warmup_session = _seeded_session(db_session, strategy=strategy)
    quiet_moment = datetime(2026, 6, 1, 23, 30, tzinfo=UTC)
    warmup_session.next_micro_session_at = quiet_moment
    db_session.commit()

    process_due_warmup_dispatches(
        db_session, worker_id="worker-1", now=quiet_moment, rng=random.Random(0)
    )

    db_session.refresh(warmup_session)
    # daily_counters must remain empty since dispatch was deferred
    assert warmup_session.daily_counters_json == {}
    # next_micro_session_at rescheduled forward (>= quiet hours end which is 08:00)
    assert _as_utc(warmup_session.next_micro_session_at) > quiet_moment
    skipped_events = [
        event
        for event in warmup_session.events
        if event.event_type == "task_skipped" and event.payload_json.get("reason") == "quiet_hours"
    ]
    assert skipped_events, "dispatch should record a quiet_hours skip event"


def test_dispatch_reschedules_into_future(db_session) -> None:
    strategy = _seed_shadow_strategy(db_session)
    warmup_session = _seeded_session(db_session, strategy=strategy)
    when = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    rng = random.Random(3)

    process_due_warmup_dispatches(db_session, worker_id="worker-1", now=when, rng=rng)

    db_session.refresh(warmup_session)
    assert warmup_session.next_micro_session_at is not None
    next_micro = _as_utc(warmup_session.next_micro_session_at)
    assert next_micro > when
    assert next_micro < when + timedelta(days=2)


def test_dispatch_skips_live_session_when_adapter_unavailable(db_session, monkeypatch) -> None:
    """When adapter.is_available() returns False for a live session, dispatch writes
    task_skipped(reason=passive_disabled) and does NOT process the session."""
    from app.adapters.warmup_tdlib import UnavailableWarmupTdlibAdapter

    monkeypatch.setattr(settings, "warmup_live_enabled", True)
    strategy = WarmupStrategy(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        name=f"Passive {new_id()[:6]}",
        description="Passive test",
        tier_limits_json={"cadence_hours": 24, "profile_required": True},
        target_channels_json=[],
        is_preset=False,
        execution_mode=WarmupExecutionMode.PASSIVE.value,
        preset_kind=WarmupPresetKind.STANDARD.value,
        duration_days=3,
        daily_action_limits_json={
            "1": {"feed_read": 1},
            "2": {"feed_read": 1},
            "3": {"feed_read": 1},
        },
        session_window_config_json={"micro_sessions_per_day": {"min": 2, "max": 4}},
        ui_summary_json={},
    )
    db_session.add(strategy)
    db_session.commit()

    account = _seed_account(db_session)
    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        now=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )

    # Use a mock adapter that reports itself as unavailable
    unavailable_adapter = UnavailableWarmupTdlibAdapter("test_passive_disabled")
    when = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    processed = process_due_warmup_dispatches(
        db_session,
        worker_id="worker-1",
        now=when,
        passive_adapter=unavailable_adapter,
    )

    assert processed == 0  # session produced no state change
    db_session.refresh(warmup_session)
    skipped_events = [
        event
        for event in warmup_session.events
        if event.event_type == "task_skipped"
        and event.payload_json.get("reason") == "passive_disabled"
    ]
    assert skipped_events, (
        "should write task_skipped(passive_disabled) for unavailable live adapter"
    )
    # daily counters must be untouched
    assert warmup_session.daily_counters_json == {}
