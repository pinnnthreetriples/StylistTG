from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import DEFAULT_LOCAL_USER_ID, DEFAULT_LOCAL_WORKSPACE_ID, WarmupEvent, WarmupSession
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated, require_mutation_permission
from app.modules.warmup.cyclic import (
    compute_total_active_hours,
    is_in_active_window,
    setup_cyclic_warmup,
)
from app.services.warmup_dispatch import process_due_warmup_dispatches
from tests.helpers.warmup import seed_warmup_account, seed_warmup_session, seed_warmup_strategy


def test_is_in_active_window_supports_dst_and_midnight_wrap() -> None:
    config = {
        "start_hour": 22,
        "end_hour": 2,
        "days_total": 7,
        "started_at": "2026-06-05T00:00:00+00:00",
    }

    assert is_in_active_window(
        config,
        datetime(2026, 6, 5, 20, 30, tzinfo=UTC),
        "Europe/Moscow",
    )
    assert not is_in_active_window(
        config,
        datetime(2026, 6, 5, 23, 30, tzinfo=UTC),
        "Europe/Moscow",
    )
    assert is_in_active_window(
        {
            "start_hour": 1,
            "end_hour": 4,
            "days_total": 1,
            "started_at": "2026-03-08T05:00:00+00:00",
        },
        datetime(2026, 3, 8, 7, 30, tzinfo=UTC),
        "America/New_York",
    )


def test_compute_total_active_hours_for_seven_day_cycle() -> None:
    assert compute_total_active_hours({"start_hour": 15, "end_hour": 18, "days_total": 7}) == 21


def test_setup_cyclic_warmup_creates_session_with_cycle_config(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    seed_warmup_strategy(db_session, is_preset=True)

    warmup_session = setup_cyclic_warmup(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        start_hour=15,
        end_hour=18,
        days_total=7,
        strategy_preset="standard",
        now=datetime(2026, 6, 5, 10, 0, tzinfo=UTC),
    )

    assert warmup_session.duration_days == 7
    assert warmup_session.cycle_config_json["start_hour"] == 15
    assert warmup_session.cycle_config_json["end_hour"] == 18
    assert warmup_session.cycle_config_json["active_hours_total"] == 21
    assert "cyclic.started" in _warmup_event_types(db_session, warmup_session.id)


def test_dispatch_skips_cyclic_session_outside_window(db_session: Session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode="shadow",
        daily_action_limits={"1": {"feed_read": 1}},
        target_channels=[],
    )
    account = seed_warmup_account(db_session)
    now = datetime(2026, 6, 5, 10, 0, tzinfo=UTC)
    warmup_session = seed_warmup_session(db_session, account=account, strategy=strategy, now=now)
    warmup_session.next_micro_session_at = now
    warmup_session.next_step_at = now
    warmup_session.timezone = "UTC"
    warmup_session.cycle_config_json = {
        "start_hour": 15,
        "end_hour": 18,
        "days_total": 7,
        "current_cycle": 1,
        "started_at": now.isoformat(),
    }
    db_session.commit()

    processed = process_due_warmup_dispatches(db_session, worker_id="worker-1", now=now)

    assert processed == 0
    assert warmup_session.next_micro_session_at == datetime(2026, 6, 5, 15, 0, tzinfo=UTC)
    events = [
        event.payload_json
        for event in db_session.execute(
            select(WarmupEvent).where(WarmupEvent.session_id == warmup_session.id)
        ).scalars()
        if event.event_type == "task_skipped"
    ]
    assert any(event.get("reason") == "cyclic_inactive_window" for event in events)


def test_cyclic_api_creates_session(
    db_session: Session,
    app_client: TestClient,
) -> None:
    account = seed_warmup_account(db_session)
    seed_warmup_strategy(db_session, is_preset=True)
    auth = AuthContext(
        user_id=DEFAULT_LOCAL_USER_ID,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="operator",
        auth_source="test",
    )
    app.dependency_overrides[require_authenticated] = lambda: auth
    app.dependency_overrides[require_mutation_permission] = lambda: auth

    response = app_client.post(
        "/api/warmup-sessions/cyclic",
        json={
            "account_ids": [account.id],
            "start_hour": 15,
            "end_hour": 18,
            "days_total": 7,
            "strategy_preset": "standard",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["items"][0]["cycle_config"]["active_hours_total"] == 21
    row = db_session.scalar(select(WarmupSession).where(WarmupSession.account_id == account.id))
    assert row is not None
    assert row.cycle_config_json["days_total"] == 7


def _warmup_event_types(session: Session, session_id: str) -> list[str]:
    return list(
        session.execute(
            select(WarmupEvent.event_type).where(WarmupEvent.session_id == session_id)
        ).scalars()
    )
