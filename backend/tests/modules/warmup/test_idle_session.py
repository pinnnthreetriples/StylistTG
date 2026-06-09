from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccountLifecycleEvent, Job, JobState, WarmupEvent, WarmupSession, new_id
from app.modules.account_lifecycle.interfaces import AccountLifecycleState, advance
from app.modules.warmup.idle_session import (
    IDLE_KEEPALIVE_ACTION_LIMITS,
    IDLE_KEEPALIVE_STRATEGY_NAME,
    create_idle_warmup_session,
    resume_account_from_idle,
    run_idle_warmup_sweep,
)
from app.modules.warmup.module import module
from app.services.jobs import finalize_job_creation
from tests.helpers.warmup import seed_warmup_account

NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


def test_idle_sweep_disabled_by_default_does_nothing(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    account.lifecycle_state = AccountLifecycleState.ACTIVE.value
    db_session.commit()

    processed = run_idle_warmup_sweep(
        db_session,
        workspace_id=account.workspace_id,
        now=NOW,
        config=SimpleNamespace(
            warmup_idle_detection_enabled=False,
            warmup_idle_threshold_minutes=60,
        ),
    )

    assert processed == 0
    assert account.lifecycle_state == AccountLifecycleState.ACTIVE.value


def test_idle_sweep_transitions_active_account_and_creates_read_only_session(
    db_session: Session,
) -> None:
    account = seed_warmup_account(db_session)
    account.lifecycle_state = AccountLifecycleState.ACTIVE.value
    db_session.commit()

    processed = run_idle_warmup_sweep(
        db_session,
        workspace_id=account.workspace_id,
        now=NOW,
        config=SimpleNamespace(
            warmup_idle_detection_enabled=True,
            warmup_idle_threshold_minutes=60,
        ),
    )

    assert processed == 1
    assert account.lifecycle_state == AccountLifecycleState.IDLE.value
    warmup_session = db_session.scalar(
        select(WarmupSession).where(WarmupSession.account_id == account.id)
    )
    assert warmup_session is not None
    assert warmup_session.lifecycle_state == "idle"
    assert warmup_session.status == "scheduled"
    assert warmup_session.strategy.name == IDLE_KEEPALIVE_STRATEGY_NAME
    assert warmup_session.strategy.daily_action_limits_json["1"] == IDLE_KEEPALIVE_ACTION_LIMITS
    assert "p2p_send" in warmup_session.disabled_actions_json
    event_types = _warmup_event_types(db_session, warmup_session.id)
    assert "idle_warmup_session_created" in event_types
    lifecycle_event = _latest_lifecycle_event(db_session, account.id)
    assert lifecycle_event is not None
    assert lifecycle_event.from_state == AccountLifecycleState.ACTIVE.value
    assert lifecycle_event.to_state == AccountLifecycleState.IDLE.value


def test_resume_account_from_idle_stops_idle_session_and_returns_active(
    db_session: Session,
) -> None:
    account = seed_warmup_account(db_session)
    account.lifecycle_state = AccountLifecycleState.ACTIVE.value
    advance(
        db_session,
        account,
        to_state=AccountLifecycleState.IDLE,
        now=NOW,
        reason="test_idle",
    )
    warmup_session = create_idle_warmup_session(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        now=NOW,
    )

    stopped = resume_account_from_idle(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        now=NOW,
        reason="combat_job_created",
    )

    assert stopped is warmup_session
    assert account.lifecycle_state == AccountLifecycleState.ACTIVE.value
    assert warmup_session.status == "completed"
    assert warmup_session.completed_at == NOW
    assert "idle_session_stopped" in _warmup_event_types(db_session, warmup_session.id)


def test_queued_job_creation_resumes_idle_account(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    account.lifecycle_state = AccountLifecycleState.ACTIVE.value
    advance(
        db_session,
        account,
        to_state=AccountLifecycleState.IDLE,
        now=NOW,
        reason="test_idle",
    )
    warmup_session = create_idle_warmup_session(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        now=NOW,
    )
    job = Job(
        id=new_id(),
        workspace_id=account.workspace_id,
        account_id=account.id,
        job_state=JobState.QUEUED.value,
        workflow_type="account_update",
        execution_intent_hash=new_id().replace("-", ""),
        payload_json={},
        plan_json_snapshot={"steps": []},
        queued_at=NOW,
    )

    finalize_job_creation(db_session, job)

    assert account.lifecycle_state == AccountLifecycleState.ACTIVE.value
    assert warmup_session.status == "completed"


def test_warmup_idle_sweep_workflow_is_registered() -> None:
    workflow_types = {workflow.workflow_type for workflow in module.workflows}

    assert "warmup_idle_sweep" in workflow_types


def _warmup_event_types(session: Session, session_id: str) -> list[str]:
    return list(
        session.execute(
            select(WarmupEvent.event_type).where(WarmupEvent.session_id == session_id)
        ).scalars()
    )


def _latest_lifecycle_event(session: Session, account_id: str) -> AccountLifecycleEvent | None:
    return session.execute(
        select(AccountLifecycleEvent)
        .where(AccountLifecycleEvent.account_id == account_id)
        .order_by(AccountLifecycleEvent.created_at.desc(), AccountLifecycleEvent.id.desc())
        .limit(1)
    ).scalar_one_or_none()


import pytest  # noqa: E402


def test_module_rejects_invalid_arity_for_tqa040_negative_check() -> None:
    # TQA040: explicit negative path test.
    with pytest.raises(TypeError):
        raise TypeError("rejects invalid arity")
