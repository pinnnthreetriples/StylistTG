from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccountLifecycleEvent, WarmupExecutionMode
from app.modules.account_lifecycle.interfaces import AccountLifecycleState, advance
from app.modules.account_safety.quarantine import create_quarantine
from app.modules.warmup.cold_soak import advance_from_cold_soak
from app.modules.warmup.dispatch_results import _complete_dispatch_session
from app.services.warmup import create_warmup_session
from tests.helpers.warmup import seed_warmup_account, seed_warmup_strategy

NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


def test_create_warmup_session_moves_account_to_cold_soak(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    strategy = seed_warmup_strategy(db_session, execution_mode=WarmupExecutionMode.DRY_RUN.value)

    create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=account.workspace_id,
        now=NOW,
    )

    assert account.lifecycle_state == AccountLifecycleState.COLD_SOAK.value
    event = _latest_transition(db_session, account.id)
    assert event is not None
    assert event.from_state == AccountLifecycleState.IMPORTED.value
    assert event.to_state == AccountLifecycleState.COLD_SOAK.value


def test_advance_from_cold_soak_moves_account_to_warming(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    strategy = seed_warmup_strategy(db_session, execution_mode=WarmupExecutionMode.DRY_RUN.value)
    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=account.workspace_id,
        now=NOW,
    )

    assert advance_from_cold_soak(db_session, warmup_session, NOW + timedelta(hours=12)) is True

    assert account.lifecycle_state == AccountLifecycleState.WARMING.value
    event = _latest_transition(db_session, account.id)
    assert event is not None
    assert event.from_state == AccountLifecycleState.COLD_SOAK.value
    assert event.to_state == AccountLifecycleState.WARMING.value


def test_complete_warmup_session_moves_account_to_pre_production(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    strategy = seed_warmup_strategy(db_session, execution_mode=WarmupExecutionMode.DRY_RUN.value)
    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=account.workspace_id,
        now=NOW,
    )
    advance_from_cold_soak(db_session, warmup_session, NOW + timedelta(hours=12))

    _complete_dispatch_session(db_session, warmup_session, now=NOW + timedelta(days=3))

    assert account.lifecycle_state == AccountLifecycleState.PRE_PRODUCTION.value
    event = _latest_transition(db_session, account.id)
    assert event is not None
    assert event.from_state == AccountLifecycleState.WARMING.value
    assert event.to_state == AccountLifecycleState.PRE_PRODUCTION.value


def test_quarantine_moves_active_account_back_to_cold_soak(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    account.lifecycle_state = AccountLifecycleState.PRE_PRODUCTION.value
    advance(
        db_session,
        account,
        to_state=AccountLifecycleState.ACTIVE,
        now=NOW,
        reason="test_active",
    )

    create_quarantine(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        reason="flood_wait",
        duration_hours=24,
    )

    assert account.lifecycle_state == AccountLifecycleState.COLD_SOAK.value
    event = _latest_transition(db_session, account.id)
    assert event is not None
    assert event.from_state == AccountLifecycleState.ACTIVE.value
    assert event.to_state == AccountLifecycleState.COLD_SOAK.value


def _latest_transition(session: Session, account_id: str) -> AccountLifecycleEvent | None:
    return session.execute(
        select(AccountLifecycleEvent)
        .where(AccountLifecycleEvent.account_id == account_id)
        .where(AccountLifecycleEvent.event_type == "account.lifecycle.transition")
        .order_by(AccountLifecycleEvent.created_at.desc(), AccountLifecycleEvent.id.desc())
        .limit(1)
    ).scalar_one_or_none()
