from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.models import (
    AccountRuntimeState,
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    WarmupExecutionMode,
    WarmupSession,
    WarmupStatus,
    WarmupStrategy,
    new_id,
)
from app.modules.warmup.enqueue import enqueue_due_warmup_dispatch_sessions
from app.modules.warmup.jobs import run_warmup_dispatch_session
from app.services.accounts import create_account

NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


def test_enqueue_due_dispatch_sessions_staggers_per_workspace(
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.config.settings.warmup_connection_stagger_min_seconds", 15)
    monkeypatch.setattr("app.config.settings.warmup_connection_stagger_max_seconds", 30)
    sessions = [_seed_live_session(db_session, due_at=NOW - timedelta(minutes=1)) for _ in range(10)]
    queue = _FakeQueue()

    ok = enqueue_due_warmup_dispatch_sessions(
        db_session,
        now=NOW,
        queue=queue,
        rng=_FixedRng([15] * 10),
        limit=10,
    )

    assert ok is True
    assert len(queue.calls) == 10
    scheduled_at = [call.scheduled_at for call in queue.calls]
    assert scheduled_at[0] == NOW + timedelta(seconds=15)
    assert [
        int((right - left).total_seconds())
        for left, right in zip(scheduled_at, scheduled_at[1:], strict=False)
    ] == [15] * 9
    assert {call.func for call in queue.calls} == {run_warmup_dispatch_session}
    assert {call.args[0] for call in queue.calls} == {item.id for item in sessions}
    for item in sessions:
        db_session.refresh(item)
        assert _as_utc(item.next_micro_session_at) > NOW
        assert any(event.event_type == "connection_stagger_scheduled" for event in item.events)


def test_run_warmup_dispatch_session_returns_zero_before_scheduled_at() -> None:
    scheduled_at = (NOW + timedelta(seconds=15)).isoformat()

    assert run_warmup_dispatch_session("session-1", scheduled_at, now=NOW) == 0


def _seed_live_session(db_session, *, due_at: datetime) -> WarmupSession:
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
    strategy = WarmupStrategy(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        name=f"Live {new_id()[:8]}",
        description="Live stagger test",
        tier_limits_json={},
        target_channels_json=[],
        is_preset=False,
        execution_mode=WarmupExecutionMode.PASSIVE.value,
        duration_days=14,
    )
    warmup_session = WarmupSession(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_id=account.id,
        strategy_id=strategy.id,
        status=WarmupStatus.ACTIVE.value,
        current_day=0,
        cadence_hours=24,
        execution_mode=WarmupExecutionMode.PASSIVE.value,
        duration_days=14,
        next_step_at=due_at,
        next_micro_session_at=due_at,
    )
    db_session.add_all([strategy, warmup_session])
    db_session.commit()
    return warmup_session


@dataclass
class _ScheduledCall:
    scheduled_at: datetime
    func: Any
    args: tuple[Any, ...]
    job_id: str | None


class _FakeQueue:
    def __init__(self) -> None:
        self.calls: list[_ScheduledCall] = []

    def enqueue_at(self, scheduled_at: datetime, func: Any, *args: Any, job_id: str | None = None) -> None:
        self.calls.append(_ScheduledCall(scheduled_at, func, args, job_id))


class _FixedRng:
    def __init__(self, values: list[int]) -> None:
        self.values = values

    def randint(self, a: int, b: int) -> int:
        del a, b
        return self.values.pop(0)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
