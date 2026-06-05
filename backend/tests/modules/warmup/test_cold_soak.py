from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WarmupEvent, WarmupExecutionMode, WarmupStatus
from app.modules.warmup.cold_soak import advance_from_cold_soak
from app.modules.warmup.readiness import validate_warmup_readiness
from app.services.warmup import create_warmup_session
from app.services.warmup_worker import process_due_warmup_sessions
from tests.helpers.warmup import seed_warmup_account, seed_warmup_strategy

NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


def test_create_warmup_session_starts_cold_soak(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr("app.modules.warmup.cold_soak.settings.warmup_cold_soak_min_hours", 12)
    monkeypatch.setattr("app.modules.warmup.cold_soak.settings.warmup_cold_soak_max_hours", 12)
    account = seed_warmup_account(db_session)
    strategy = seed_warmup_strategy(db_session, execution_mode=WarmupExecutionMode.DRY_RUN.value)

    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=account.workspace_id,
        now=NOW,
    )

    assert warmup_session.status == WarmupStatus.COLD_SOAK.value
    assert _without_tz(warmup_session.cold_soak_until) == _without_tz(NOW + timedelta(hours=12))
    event_types = _event_types(db_session, warmup_session.id)
    assert event_types[0] == "session_created"
    assert set(event_types[1:]) == {"proxy_adaptation_applied", "cold_soak_started"}


def test_due_worker_skips_early_cold_soak_tick_once_per_hour(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr("app.modules.warmup.cold_soak.settings.warmup_cold_soak_min_hours", 12)
    monkeypatch.setattr("app.modules.warmup.cold_soak.settings.warmup_cold_soak_max_hours", 12)
    account = seed_warmup_account(db_session)
    strategy = seed_warmup_strategy(db_session, execution_mode=WarmupExecutionMode.DRY_RUN.value)
    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=account.workspace_id,
        now=NOW,
    )
    warmup_session.next_step_at = NOW
    db_session.commit()

    processed = process_due_warmup_sessions(db_session, worker_id="worker-1", now=NOW)
    warmup_session.next_step_at = NOW + timedelta(minutes=30)
    db_session.commit()
    processed_again = process_due_warmup_sessions(
        db_session,
        worker_id="worker-1",
        now=NOW + timedelta(minutes=30),
    )

    assert processed == 0
    assert processed_again == 0
    assert _event_types(db_session, warmup_session.id).count("cold_soak_in_progress") == 1


def test_due_worker_advances_expired_cold_soak_and_runs_dry_day(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr("app.modules.warmup.cold_soak.settings.warmup_cold_soak_min_hours", 12)
    monkeypatch.setattr("app.modules.warmup.cold_soak.settings.warmup_cold_soak_max_hours", 12)
    account = seed_warmup_account(db_session)
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.DRY_RUN.value,
        duration_days=3,
    )
    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=account.workspace_id,
        now=NOW,
    )
    due_at = NOW + timedelta(hours=12)

    processed = process_due_warmup_sessions(db_session, worker_id="worker-1", now=due_at)
    db_session.refresh(warmup_session)

    assert processed == 1
    assert warmup_session.status == WarmupStatus.ACTIVE.value
    assert warmup_session.current_day == 1
    assert {"cold_soak_completed", "task_executed"}.issubset(
        set(_event_types(db_session, warmup_session.id))
    )


def test_advance_from_cold_soak_is_idempotent(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr("app.modules.warmup.cold_soak.settings.warmup_cold_soak_min_hours", 12)
    monkeypatch.setattr("app.modules.warmup.cold_soak.settings.warmup_cold_soak_max_hours", 12)
    account = seed_warmup_account(db_session)
    strategy = seed_warmup_strategy(db_session, execution_mode=WarmupExecutionMode.DRY_RUN.value)
    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=account.workspace_id,
        now=NOW,
    )
    due_at = NOW + timedelta(hours=12)

    assert advance_from_cold_soak(db_session, warmup_session, due_at) is True
    assert advance_from_cold_soak(db_session, warmup_session, due_at) is False
    assert warmup_session.status == WarmupStatus.SCHEDULED.value


def test_cold_soak_session_blocks_duplicate_warmup_readiness(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr("app.modules.warmup.cold_soak.settings.warmup_cold_soak_min_hours", 12)
    monkeypatch.setattr("app.modules.warmup.cold_soak.settings.warmup_cold_soak_max_hours", 12)
    account = seed_warmup_account(db_session)
    strategy = seed_warmup_strategy(db_session, execution_mode=WarmupExecutionMode.DRY_RUN.value)
    create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=account.workspace_id,
        now=NOW,
    )

    readiness = validate_warmup_readiness(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=account.workspace_id,
    )

    assert "Для аккаунта уже есть активная подготовка" in readiness.blocking_reasons


def _event_types(session: Session, session_id: str) -> list[str]:
    return list(
        session.execute(
            select(WarmupEvent.event_type)
            .where(WarmupEvent.session_id == session_id)
            .order_by(WarmupEvent.created_at.asc(), WarmupEvent.id.asc())
        ).scalars()
    )


def _without_tz(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=None)
