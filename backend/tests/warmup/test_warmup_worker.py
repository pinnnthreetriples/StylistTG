from datetime import UTC, datetime

from app.models import (
    AccountRuntimeState,
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    WarmupEvent,
    WarmupSession,
    WarmupStatus,
    WarmupStrategy,
    WarmupTaskRun,
    WarmupTaskRunStatus,
    new_id,
)
from app.services.accounts import create_account
from app.services.warmup_worker import claim_account_runtime_lock, handle_warmup_step_failure, process_due_warmup_sessions


def test_due_warmup_session_advances_one_day(db_session) -> None:
    session = _seed_session(db_session, current_day=0, next_step_at=datetime(2026, 5, 5, 12, tzinfo=UTC))

    processed = _process_due(db_session, session, now=datetime(2026, 5, 5, 12, tzinfo=UTC))

    assert processed == 1
    assert session.current_day == 1
    assert session.status == WarmupStatus.ACTIVE
    assert _as_utc(session.next_step_at) == datetime(2026, 5, 6, 12, tzinfo=UTC)
    assert db_session.query(WarmupTaskRun).count() == 1


def test_not_due_warmup_session_is_skipped(db_session) -> None:
    session = _seed_session(db_session, current_day=0, next_step_at=datetime(2026, 5, 6, 12, tzinfo=UTC))

    processed = _process_due(db_session, session, now=datetime(2026, 5, 5, 12, tzinfo=UTC))

    assert processed == 0
    assert session.current_day == 0
    assert db_session.query(WarmupTaskRun).count() == 0


def test_duplicate_task_run_is_idempotently_skipped(db_session) -> None:
    session = _seed_session(db_session, current_day=0, next_step_at=datetime(2026, 5, 5, 12, tzinfo=UTC))
    db_session.add(
        WarmupTaskRun(
            id=new_id(),
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            session_id=session.id,
            day=0,
            task_type="dry_run_day",
            status=WarmupTaskRunStatus.COMPLETED,
            metadata_json={},
        )
    )
    db_session.commit()

    processed = _process_due(db_session, session, now=datetime(2026, 5, 5, 12, tzinfo=UTC))

    assert processed == 0
    assert session.current_day == 0
    assert db_session.query(WarmupTaskRun).count() == 1
    assert db_session.query(WarmupEvent).filter_by(event_type="task_skipped").count() == 1


def test_day_13_step_completes_session_at_day_14(db_session) -> None:
    session = _seed_session(db_session, current_day=13, next_step_at=datetime(2026, 5, 5, 12, tzinfo=UTC))

    processed = _process_due(db_session, session, now=datetime(2026, 5, 5, 12, tzinfo=UTC))

    assert processed == 1
    assert session.current_day == 14
    assert session.status == WarmupStatus.COMPLETED
    assert _as_utc(session.completed_at) == datetime(2026, 5, 5, 12, tzinfo=UTC)


def test_circuit_breaker_fails_after_threshold(db_session) -> None:
    session = _seed_session(db_session, current_day=2, next_step_at=datetime(2026, 5, 5, 12, tzinfo=UTC))
    session.consecutive_failures = 2
    db_session.commit()

    handle_warmup_step_failure(
        db_session,
        warmup_session=session,
        error="boom",
        max_failures=3,
        now=datetime(2026, 5, 5, 12, tzinfo=UTC),
    )
    db_session.refresh(session)

    assert session.status == WarmupStatus.FAILED
    assert session.consecutive_failures == 3
    assert db_session.query(WarmupEvent).filter_by(event_type="circuit_breaker_triggered").count() == 1


def test_circuit_breaker_respects_explicit_zero_max_failures(db_session) -> None:
    """Regression: max_failures=0 must trigger the breaker on the very first failure.

    Previously `max_failures or default` treated 0 as falsy and fell back to the
    global default, making the threshold impossible to set to 0.
    """
    session = _seed_session(db_session, current_day=1, next_step_at=datetime(2026, 5, 5, 12, tzinfo=UTC))
    session.consecutive_failures = 0
    db_session.commit()

    handle_warmup_step_failure(
        db_session,
        warmup_session=session,
        error="should_trip_immediately",
        max_failures=0,
        now=datetime(2026, 5, 5, 12, tzinfo=UTC),
    )
    db_session.refresh(session)

    assert session.status == WarmupStatus.FAILED
    assert session.consecutive_failures == 1
    assert db_session.query(WarmupEvent).filter_by(event_type="circuit_breaker_triggered").count() == 1


def test_account_runtime_lock_claim_uses_database_state_not_stale_identity_map(db_session) -> None:
    session = _seed_session(db_session, current_day=0, next_step_at=datetime(2026, 5, 5, 12, tzinfo=UTC))
    runtime = db_session.get(AccountRuntimeState, session.account_id)
    assert runtime is not None
    assert runtime.lock_owner is None

    db_session.execute(
        AccountRuntimeState.__table__.update()
        .where(AccountRuntimeState.account_id == session.account_id)
        .values(lock_owner="other-worker")
    )
    db_session.commit()

    claimed = claim_account_runtime_lock(
        db_session,
        account_id=session.account_id,
        owner="warmup:test-worker",
        now=datetime(2026, 5, 5, 12, tzinfo=UTC),
    )

    assert claimed is False
    db_session.refresh(runtime)
    assert runtime.lock_owner == "other-worker"


def test_session_already_at_or_past_duration_completes_immediately(db_session) -> None:
    """Regression: if current_day >= duration_days on entry (e.g. scheduler race),
    the worker should complete the session without creating a duplicate task_run."""
    session = _seed_session(db_session, current_day=14, next_step_at=datetime(2026, 5, 5, 12, tzinfo=UTC))
    session.duration_days = 14
    db_session.commit()

    processed = _process_due(db_session, session, now=datetime(2026, 5, 5, 12, tzinfo=UTC))

    assert processed == 1
    assert session.status == WarmupStatus.COMPLETED
    assert session.completed_at is not None
    assert db_session.query(WarmupTaskRun).filter_by(session_id=session.id).count() == 0


def _seed_session(db_session, *, current_day: int, next_step_at: datetime) -> WarmupSession:
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
        name=f"Стратегия {new_id()[:8]}",
        description="Тестовая стратегия",
        tier_limits_json={},
        target_channels_json=[],
        is_preset=True,
    )
    db_session.add(strategy)
    db_session.flush()
    session = WarmupSession(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_id=account.id,
        strategy_id=strategy.id,
        status=WarmupStatus.SCHEDULED,
        current_day=current_day,
        cadence_hours=24,
        next_step_at=next_step_at,
    )
    db_session.add(session)
    db_session.commit()
    return session


def _process_due(db_session, session: WarmupSession, *, now: datetime) -> int:
    """Run process_due_warmup_sessions and refresh the session row."""
    processed = process_due_warmup_sessions(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        now=now,
        worker_id="test-worker",
    )
    db_session.refresh(session)
    return processed


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)
