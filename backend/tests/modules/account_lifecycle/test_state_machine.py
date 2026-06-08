from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccountLifecycleEvent, DEFAULT_LOCAL_USER_ID
from app.modules.account_lifecycle.interfaces import (
    TRANSITION_EVENT_TYPE,
    AccountLifecycleState,
    InvalidTransitionError,
    advance,
)
from app.services.accounts import create_account

NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("from_state", "to_state", "manual"),
    [
        (AccountLifecycleState.IMPORTED, AccountLifecycleState.COLD_SOAK, False),
        (AccountLifecycleState.COLD_SOAK, AccountLifecycleState.WARMING, False),
        (AccountLifecycleState.COLD_SOAK, AccountLifecycleState.RETIRED, True),
        (AccountLifecycleState.COLD_SOAK, AccountLifecycleState.BANNED, True),
        (AccountLifecycleState.COLD_SOAK, AccountLifecycleState.DELETED, True),
        (AccountLifecycleState.WARMING, AccountLifecycleState.PRE_PRODUCTION, False),
        (AccountLifecycleState.WARMING, AccountLifecycleState.COLD_SOAK, True),
        (AccountLifecycleState.PRE_PRODUCTION, AccountLifecycleState.ACTIVE, False),
        (AccountLifecycleState.PRE_PRODUCTION, AccountLifecycleState.COLD_SOAK, False),
        (AccountLifecycleState.ACTIVE, AccountLifecycleState.IDLE, False),
        (AccountLifecycleState.ACTIVE, AccountLifecycleState.COLD_SOAK, False),
        (AccountLifecycleState.ACTIVE, AccountLifecycleState.RETIRED, True),
        (AccountLifecycleState.IDLE, AccountLifecycleState.ACTIVE, False),
        (AccountLifecycleState.IDLE, AccountLifecycleState.RETIRED, True),
    ],
)
def test_advance_allows_declared_transitions(
    db_session: Session,
    from_state: AccountLifecycleState,
    to_state: AccountLifecycleState,
    manual: bool,
) -> None:
    account = _account(db_session)
    account.lifecycle_state = from_state.value
    db_session.commit()

    event = advance(
        db_session,
        account,
        to_state=to_state,
        now=NOW,
        reason="test_transition",
        actor_user_id=DEFAULT_LOCAL_USER_ID,
        manual=manual,
        metadata={"source": "test"},
    )

    assert event is not None
    assert account.lifecycle_state == to_state.value
    assert account.lifecycle_updated_at == NOW
    assert event.event_type == TRANSITION_EVENT_TYPE
    assert event.from_state == from_state.value
    assert event.to_state == to_state.value
    assert event.reason == "test_transition"
    assert event.actor_user_id == DEFAULT_LOCAL_USER_ID
    assert event.payload_json == {"source": "test"}
    assert event.occurred_at == NOW


@pytest.mark.parametrize(
    ("from_state", "to_state", "manual"),
    [
        (AccountLifecycleState.IMPORTED, AccountLifecycleState.ACTIVE, False),
        (AccountLifecycleState.ACTIVE, AccountLifecycleState.BANNED, False),
        (AccountLifecycleState.WARMING, AccountLifecycleState.COLD_SOAK, False),
        (AccountLifecycleState.RETIRED, AccountLifecycleState.ACTIVE, True),
        (AccountLifecycleState.BANNED, AccountLifecycleState.COLD_SOAK, True),
        (AccountLifecycleState.DELETED, AccountLifecycleState.IMPORTED, True),
    ],
)
def test_advance_rejects_invalid_or_manual_only_transitions(
    db_session: Session,
    from_state: AccountLifecycleState,
    to_state: AccountLifecycleState,
    manual: bool,
) -> None:
    account = _account(db_session)
    account.lifecycle_state = from_state.value
    db_session.commit()

    with pytest.raises(InvalidTransitionError):
        advance(
            db_session,
            account,
            to_state=to_state,
            now=NOW,
            reason="invalid_transition",
            manual=manual,
        )

    assert account.lifecycle_state == from_state.value
    assert _transition_events(db_session, account.id) == []


def test_advance_same_state_is_idempotent(db_session: Session) -> None:
    account = _account(db_session)

    event = advance(
        db_session,
        account,
        to_state=AccountLifecycleState.IMPORTED,
        now=NOW,
        reason="same_state",
    )

    assert event is None
    assert _transition_events(db_session, account.id) == []


def _account(db_session: Session):
    return create_account(db_session, external_ref=f"+1555{len(db_session.identity_map):08d}")


def _transition_events(session: Session, account_id: str) -> list[AccountLifecycleEvent]:
    return list(
        session.execute(
            select(AccountLifecycleEvent).where(AccountLifecycleEvent.account_id == account_id)
        ).scalars()
    )
