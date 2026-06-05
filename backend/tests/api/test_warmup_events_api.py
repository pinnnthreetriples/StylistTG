from datetime import UTC, datetime, timedelta

from app.models import (
    AccountRuntimeState,
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    WarmupEvent,
    WarmupStrategy,
    new_id,
)
from app.modules.warmup.events import write_warmup_event
from app.services.accounts import create_account
from app.services.warmup import create_warmup_session


def test_warmup_events_endpoint_returns_live_feed_with_filters(app_client, db_session) -> None:
    account = _seed_ready_account(db_session, external_ref="+15550101000")
    other_account = _seed_ready_account(db_session, external_ref="+15550101001")
    strategy = _seed_strategy(db_session)
    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    other_session = create_warmup_session(
        db_session,
        account_id=other_account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    first = write_warmup_event(
        db_session,
        warmup_session,
        "micro_session_window_opened",
        {"day": 1},
    )
    second = write_warmup_event(
        db_session,
        warmup_session,
        "session_action_executed",
        {"action_type": "feed_read", "day": 1},
    )
    third = write_warmup_event(
        db_session,
        other_session,
        "task_failed",
        {"action_type": "feed_read", "error_code": "NETWORK_ERROR"},
    )
    _set_event_times(db_session, first=first, second=second, third=third)
    db_session.commit()

    response = app_client.get(
        f"/api/warmup-events?account_id={account.id}&severity=success&limit=10"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["next_cursor"] == second.id
    assert [item["event_id"] for item in body["items"]] == [second.id]
    assert body["items"][0]["severity"] == "success"
    assert body["items"][0]["account_label"] == "+15550101000"
    assert body["items"][0]["phone_id"] == "+15550101000"
    assert {account["account_id"] for account in body["accounts"]} == {
        account.id,
        other_account.id,
    }

    cursor_response = app_client.get(f"/api/warmup-events?cursor={first.id}&limit=10")
    assert cursor_response.status_code == 200
    assert second.id in [item["event_id"] for item in cursor_response.json()["items"]]


def test_warmup_event_severity_defaults_and_response_model(app_client, db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    event = write_warmup_event(
        db_session,
        warmup_session,
        "task_skipped",
        {"reason": "safety_gate_blocked"},
    )
    db_session.commit()

    response = app_client.get(f"/api/warmup/sessions/{warmup_session.id}/events")

    assert response.status_code == 200
    event_payload = next(item for item in response.json()["items"] if item["id"] == event.id)
    assert event_payload["severity"] == "warning"


def test_warmup_event_stream_route_is_sse(app_client, monkeypatch) -> None:
    async def fake_stream(*_args, **_kwargs):
        yield 'data: {"event_id":"evt-1"}\n\n'

    monkeypatch.setattr("app.modules.warmup.router._warmup_event_stream", fake_stream)

    with app_client.stream("GET", "/api/warmup-events/stream") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert next(response.iter_lines()) == 'data: {"event_id":"evt-1"}'


def _seed_ready_account(db_session, *, external_ref: str | None = None):
    account = create_account(
        db_session,
        external_ref=external_ref or f"+7999{new_id()[:8]}",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state = AccountRuntimeState(
        account_id=account.id,
        session_present=True,
        runtime_health="ready",
        reauth_required=False,
    )
    db_session.commit()
    return account


def _seed_strategy(db_session) -> WarmupStrategy:
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
    db_session.commit()
    return strategy


def _set_event_times(
    db_session,
    *,
    first: WarmupEvent,
    second: WarmupEvent,
    third: WarmupEvent,
) -> None:
    base = datetime(2026, 6, 5, 9, 0, tzinfo=UTC)
    for event in db_session.query(WarmupEvent).all():
        event.created_at = base - timedelta(minutes=1)
    first.created_at = base
    second.created_at = base + timedelta(seconds=1)
    third.created_at = base + timedelta(seconds=2)
