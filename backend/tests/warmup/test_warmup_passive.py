"""Phase 2 backend: passive read-only TDLib adapter contract tests.

Покрывает:
- MockWarmupTdlibAdapter возвращает структурированный WarmupActionResult
  для поддерживаемых action_type, и `unsupported` для всего прочего.
- Factory build_warmup_tdlib_adapter респектирует kill-switch
  warmup_passive_enabled.
- Dispatch для passive-сессии вызывает adapter и пишет
  session_action_executed (а не simulated).
- Если passive_enabled=False → adapter недоступен → dispatch пишет
  task_skipped reason="passive_disabled" и не двигает counters.
- Ошибки adapter поднимают consecutive_failures и пишут task_failed;
  на N подряд → circuit breaker → status=PAUSED_RISK + next_micro_session_at=None.
"""
from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from app.adapters.warmup_tdlib import (
    MockWarmupTdlibAdapter,
    UnavailableWarmupTdlibAdapter,
    WarmupActionResult,
    build_warmup_tdlib_adapter,
)
from app.config import settings
from app.models import (
    WarmupExecutionMode,
    WarmupSession,
    WarmupStatus,
    WarmupStrategy,
)
from app.services.warmup_dispatch import process_due_warmup_dispatches
from tests.helpers.warmup import seed_warmup_account, seed_warmup_session, seed_warmup_strategy


# ---------------------------------------------------------------------------
# Adapter contract tests
# ---------------------------------------------------------------------------


def test_mock_adapter_returns_ok_for_supported_actions() -> None:
    adapter = MockWarmupTdlibAdapter(rng_seed=7)

    result = adapter.execute_action(
        account_id="acc-1", action_type="feed_read", context={"proxy_category": "residential"}
    )

    assert result.is_ok
    assert result.action_type == "feed_read"
    assert "latency_ms" in result.metadata
    assert result.metadata.get("provider") == "mock"
    assert "chats_seen" in result.metadata


def test_mock_adapter_marks_unsupported_action() -> None:
    adapter = MockWarmupTdlibAdapter()

    result = adapter.execute_action(
        account_id="acc-1", action_type="send_message", context={}
    )

    assert not result.is_ok
    assert result.status == "unsupported"
    assert result.error_code == "action_not_supported_in_passive"


def test_mock_adapter_can_force_failure() -> None:
    adapter = MockWarmupTdlibAdapter(failure_action_types=("feed_read",), failure_status="flood_wait")

    result = adapter.execute_action(
        account_id="acc-1", action_type="feed_read", context={}
    )

    assert result.status == "flood_wait"
    assert result.error_code == "mock_forced_failure"


def test_factory_returns_unavailable_when_passive_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "warmup_passive_enabled", False)
    adapter = build_warmup_tdlib_adapter()
    assert isinstance(adapter, UnavailableWarmupTdlibAdapter)
    assert not adapter.is_available()
    assert (
        adapter.execute_action(
            account_id="acc-1", action_type="feed_read", context={}
        ).status
        == "unavailable"
    )


# ---------------------------------------------------------------------------
# Dispatch wiring tests
# ---------------------------------------------------------------------------


_DEFAULT_PASSIVE_LIMITS = {
    "1": {"feed_read": 2, "ping_proxy": 1, "get_me": 1},
    "2": {"feed_read": 2, "ping_proxy": 1, "get_me": 1},
    "3": {"feed_read": 2, "ping_proxy": 1, "get_me": 1},
}


def _seed_passive_strategy(
    db_session,
    *,
    duration_days: int = 3,
    daily_action_limits: dict | None = None,
) -> WarmupStrategy:
    return seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.PASSIVE.value,
        duration_days=duration_days,
        daily_action_limits=daily_action_limits or _DEFAULT_PASSIVE_LIMITS,
    )


def _seeded_passive_session(db_session, strategy: WarmupStrategy) -> WarmupSession:
    return seed_warmup_session(
        db_session,
        strategy=strategy,
        now=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
    )


def test_passive_dispatch_executes_adapter_and_writes_executed_event(db_session) -> None:
    strategy = _seed_passive_strategy(db_session)
    warmup_session = _seeded_passive_session(db_session, strategy)
    adapter = MockWarmupTdlibAdapter(rng_seed=11)
    when = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

    process_due_warmup_dispatches(
        db_session,
        worker_id="worker-1",
        now=when,
        rng=random.Random(11),
        passive_adapter=adapter,
    )

    db_session.refresh(warmup_session)
    event_types = [event.event_type for event in warmup_session.events]
    assert "session_action_executed" in event_types
    assert "session_action_simulated" not in event_types
    # adapter metadata is propagated to event payload
    executed = next(e for e in warmup_session.events if e.event_type == "session_action_executed")
    assert executed.payload_json.get("simulated") is False
    metadata = executed.payload_json.get("metadata") or {}
    assert metadata.get("provider") == "mock"
    assert "latency_ms" in metadata
    # counters incremented for at least one action
    counters = warmup_session.daily_counters_json.get("0", {})
    assert sum(counters.values()) >= 1


def test_passive_dispatch_skips_when_adapter_unavailable(db_session) -> None:
    strategy = _seed_passive_strategy(db_session)
    warmup_session = _seeded_passive_session(db_session, strategy)
    adapter = UnavailableWarmupTdlibAdapter("test_disabled")
    when = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

    process_due_warmup_dispatches(
        db_session,
        worker_id="worker-1",
        now=when,
        rng=random.Random(0),
        passive_adapter=adapter,
    )

    db_session.refresh(warmup_session)
    skipped = [
        event
        for event in warmup_session.events
        if event.event_type == "task_skipped"
        and event.payload_json.get("reason") == "passive_disabled"
    ]
    assert skipped, "expected a passive_disabled skip event"
    # counters must remain empty
    assert warmup_session.daily_counters_json == {}
    # rescheduled forward, but session not ACTIVE yet
    assert warmup_session.status == WarmupStatus.SCHEDULED.value


def test_passive_dispatch_circuit_breaker_trips_after_repeated_failures(
    db_session, monkeypatch
) -> None:
    # Force breaker after a single failed tick to keep test compact.
    monkeypatch.setattr(settings, "warmup_max_consecutive_failures", 1)
    strategy = _seed_passive_strategy(db_session)
    warmup_session = _seeded_passive_session(db_session, strategy)
    adapter = MockWarmupTdlibAdapter(
        rng_seed=0,
        failure_action_types=("feed_read", "ping_proxy", "get_me"),
        failure_status="flood_wait",
    )
    when = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

    process_due_warmup_dispatches(
        db_session,
        worker_id="worker-1",
        now=when,
        rng=random.Random(0),
        passive_adapter=adapter,
    )

    db_session.refresh(warmup_session)
    event_types = [event.event_type for event in warmup_session.events]
    assert "task_failed" in event_types
    assert "circuit_breaker_triggered" in event_types
    assert warmup_session.status == WarmupStatus.PAUSED_RISK.value
    assert warmup_session.next_micro_session_at is None
    assert warmup_session.consecutive_failures >= 1


def test_passive_dispatch_does_not_advance_day_on_failure_only(db_session) -> None:
    strategy = _seed_passive_strategy(
        db_session,
        duration_days=3,
        daily_action_limits={"1": {"feed_read": 1}},
    )
    warmup_session = _seeded_passive_session(db_session, strategy)
    adapter = MockWarmupTdlibAdapter(
        rng_seed=0,
        failure_action_types=("feed_read",),
        failure_status="flood_wait",
    )
    when = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

    process_due_warmup_dispatches(
        db_session,
        worker_id="worker-1",
        now=when,
        rng=random.Random(0),
        passive_adapter=adapter,
    )

    db_session.refresh(warmup_session)
    # day must not move because counters did not increment
    assert warmup_session.current_day == 0
    assert warmup_session.daily_counters_json.get("0", {}).get("feed_read", 0) == 0


def test_passive_dispatch_respects_retry_after_on_flood_wait(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "warmup_max_consecutive_failures", 3)
    strategy = _seed_passive_strategy(
        db_session,
        duration_days=3,
        daily_action_limits={"1": {"feed_read": 1}},
    )
    warmup_session = _seeded_passive_session(db_session, strategy)
    adapter = MockWarmupTdlibAdapter(
        rng_seed=0,
        failure_action_types=("feed_read",),
        failure_status="flood_wait",
        failure_retry_after_seconds=600,
    )
    when = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

    process_due_warmup_dispatches(
        db_session,
        worker_id="worker-1",
        now=when,
        rng=random.Random(0),
        passive_adapter=adapter,
    )

    db_session.refresh(warmup_session)
    retry_at = when + timedelta(seconds=600)
    assert warmup_session.status == WarmupStatus.SCHEDULED.value
    assert warmup_session.next_attempt_at == retry_at.replace(tzinfo=None)
    assert warmup_session.next_micro_session_at == retry_at.replace(tzinfo=None)


def test_shadow_dispatch_does_not_call_passive_adapter(db_session) -> None:
    """Phase 2 contract: shadow stays in pure simulation mode."""
    from app.models import WarmupExecutionMode as ExMode

    account = seed_warmup_account(db_session)
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=ExMode.SHADOW.value,
        daily_action_limits={"1": {"feed_read": 1}},
    )
    warmup_session = seed_warmup_session(
        db_session,
        account=account,
        strategy=strategy,
        now=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
    )

    calls: list[str] = []

    class TrackingAdapter:
        provider_name = "tracking"

        def is_available(self) -> bool:
            return True

        def execute_action(self, *, account_id, action_type, context):
            calls.append(action_type)
            return WarmupActionResult(status="ok", action_type=action_type)

    process_due_warmup_dispatches(
        db_session,
        worker_id="worker-1",
        now=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
        rng=random.Random(0),
        passive_adapter=TrackingAdapter(),
    )

    db_session.refresh(warmup_session)
    assert calls == [], "shadow execution_mode must not invoke passive adapter"
    event_types = [event.event_type for event in warmup_session.events]
    assert "session_action_simulated" in event_types
    assert "session_action_executed" not in event_types
