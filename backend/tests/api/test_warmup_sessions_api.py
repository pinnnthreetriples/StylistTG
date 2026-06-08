from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time

from app.models import (
    AccountRuntimeState,
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    WarmupExecutionMode,
    WarmupEvent,
    WarmupIsolationClaim,
    WarmupPresetKind,
    WarmupSession,
    WarmupStatus,
    WarmupStrategy,
    new_id,
)
from app.modules.warmup.errors import WarmupIsolationConflictError
from app.services.accounts import create_account
from app.services.warmup import (
    create_warmup_session,
    delete_warmup_session,
    get_warmup_session,
    list_warmup_events,
    list_warmup_sessions,
    pause_warmup_session,
    resume_warmup_session,
)
from app.services.warmup_isolation import acquire_claim


def test_create_warmup_session_schedules_session_and_writes_event(db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    now = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)

    created = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        now=now,
    )
    db_session.commit()

    assert created.status == WarmupStatus.COLD_SOAK
    assert created.current_day == 0
    assert created.cadence_hours == 24
    assert created.cold_soak_until is not None
    assert created.next_step_at == created.cold_soak_until
    events = db_session.query(WarmupEvent).order_by(WarmupEvent.created_at.asc()).all()
    assert [event.event_type for event in events] == ["session_created", "cold_soak_started"]
    assert {event.session_id for event in events} == {created.id}


def test_create_warmup_session_rejects_blocked_readiness(db_session) -> None:
    account = create_account(
        db_session,
        external_ref=f"+7999{new_id()[:8]}",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    strategy = _seed_strategy(db_session)

    with pytest.raises(ValueError, match="Аккаунт не готов"):
        create_warmup_session(
            db_session,
            account_id=account.id,
            strategy_id=strategy.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        )


def test_create_warmup_session_rejects_duplicate_active_session(db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    first = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    db_session.commit()

    with pytest.raises(ValueError, match="активная подготовка"):
        create_warmup_session(
            db_session,
            account_id=account.id,
            strategy_id=first.strategy_id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        )


def test_create_live_warmup_session_raises_typed_isolation_conflict(db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    strategy.execution_mode = WarmupExecutionMode.SHADOW.value
    acquire_claim(
        db_session,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        held_by="warmup:other-session",
        reason="existing warmup",
    )
    db_session.commit()

    with pytest.raises(WarmupIsolationConflictError) as excinfo:
        create_warmup_session(
            db_session,
            account_id=account.id,
            strategy_id=strategy.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        )

    assert excinfo.value.legacy_message == "account is already isolated by another warmup session"


def test_list_detail_status_and_events(db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    created = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    db_session.commit()

    items, total = list_warmup_sessions(db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID)
    detail = get_warmup_session(
        db_session, session_id=created.id, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID
    )
    events, event_total = list_warmup_events(
        db_session,
        session_id=created.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert total == 1
    assert items[0].id == created.id
    assert detail.id == created.id
    assert event_total == 2
    assert {event.event_type for event in events} == {"session_created", "cold_soak_started"}


def test_delete_warmup_session_removes_session_and_events(db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    created = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    db_session.commit()

    delete_warmup_session(
        db_session,
        session_id=created.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    db_session.commit()

    assert db_session.query(WarmupSession).count() == 0
    assert db_session.query(WarmupEvent).count() == 0


@freeze_time("2026-01-15 12:00:00")
def test_pause_and_resume_warmup_session(db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    created = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    created.status = WarmupStatus.SCHEDULED
    db_session.commit()

    paused = pause_warmup_session(
        db_session,
        session_id=created.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        reason="Проверка proxy",
    )
    resumed = resume_warmup_session(
        db_session,
        session_id=created.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        now=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.commit()

    assert paused.id == created.id
    assert resumed.status == WarmupStatus.SCHEDULED
    assert db_session.query(WarmupEvent).filter_by(event_type="paused").count() == 1
    assert db_session.query(WarmupEvent).filter_by(event_type="resumed").count() == 1


def test_resume_rejects_future_retry(db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    created = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    created.status = WarmupStatus.PAUSED_RISK
    created.next_attempt_at = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    db_session.commit()

    with pytest.raises(ValueError, match="retry_not_ready"):
        resume_warmup_session(
            db_session,
            session_id=created.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            now=datetime(2026, 5, 5, 12, 0, tzinfo=UTC),
        )


def test_create_warmup_session_endpoint_skips_enqueue_when_workers_disabled(
    app_client, db_session, monkeypatch
) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    enqueued: list[str] = []

    monkeypatch.setattr(
        "app.modules.warmup.commands.enqueue_warmup_due_sessions",
        lambda: enqueued.append("warmup") or True,
    )

    response = _post_warmup_session(app_client, account.id, strategy.id)

    assert response.status_code == 201
    assert enqueued == []


def test_create_warmup_session_endpoint_enqueues_due_worker_when_enabled(
    app_client, db_session, monkeypatch
) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    enqueued: list[str] = []

    monkeypatch.setattr("app.modules.warmup.service.settings.warmup_workers_enabled", True)
    monkeypatch.setattr(
        "app.modules.warmup.commands.enqueue_warmup_due_sessions",
        lambda: enqueued.append("warmup") or True,
    )

    response = _post_warmup_session(app_client, account.id, strategy.id)

    assert response.status_code == 201
    assert enqueued == ["warmup"]


def test_create_warmup_session_marks_session_failed_when_enqueue_fails(
    app_client, db_session, monkeypatch
) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)

    monkeypatch.setattr("app.modules.warmup.service.settings.warmup_workers_enabled", True)
    monkeypatch.setattr("app.modules.warmup.commands.enqueue_warmup_due_sessions", lambda: False)

    response = _post_warmup_session(app_client, account.id, strategy.id)

    assert response.status_code == 503
    warmup_session = db_session.query(WarmupSession).one()
    assert warmup_session.status == WarmupStatus.FAILED
    assert db_session.query(WarmupEvent).filter_by(event_type="queue_enqueue_failed").count() == 1


def test_delete_warmup_session_endpoint(app_client, db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    created = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    db_session.commit()

    response = app_client.delete(f"/api/warmup/sessions/{created.id}")

    assert response.status_code == 204
    assert db_session.query(WarmupSession).count() == 0


def test_delete_warmup_session_releases_isolation_claim(db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_shadow_strategy(db_session)
    created = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    db_session.commit()

    assert db_session.get(WarmupIsolationClaim, account.id) is not None

    delete_warmup_session(
        db_session,
        session_id=created.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    db_session.commit()

    assert db_session.get(WarmupIsolationClaim, account.id) is None


def test_isolation_status_returns_unisolated_for_dry_run_session(app_client, db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    _create_session(db_session, account.id, strategy.id)

    response = app_client.get(f"/api/warmup/isolation/by-account/{account.id}")

    assert response.status_code == 200
    body = response.json()
    assert body == {"is_isolated": False, "claim": None}


def test_isolation_status_returns_claim_for_shadow_session(app_client, db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_shadow_strategy(db_session)

    warmup_session = _create_session(db_session, account.id, strategy.id)

    response = app_client.get(f"/api/warmup/isolation/by-account/{account.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["is_isolated"] is True
    assert body["claim"] is not None
    assert body["claim"]["account_id"] == account.id
    assert body["claim"]["held_by"] == f"warmup:{warmup_session.id}"
    assert "shadow" in body["claim"]["reason"]


def test_isolation_status_returns_404_for_unknown_account(app_client, db_session) -> None:
    response = app_client.get(f"/api/warmup/isolation/by-account/{new_id()}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "ACCOUNT_NOT_FOUND"


def test_create_shadow_session_enqueues_dispatch_worker_when_workers_enabled(
    app_client, db_session, monkeypatch
) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_shadow_strategy(db_session)
    enqueued: list[str] = []

    monkeypatch.setattr("app.modules.warmup.service.settings.warmup_workers_enabled", True)
    monkeypatch.setattr(
        "app.modules.warmup.commands.enqueue_warmup_due_sessions",
        lambda: enqueued.append("dry") or True,
    )
    monkeypatch.setattr(
        "app.modules.warmup.commands.enqueue_warmup_dispatch_tick",
        lambda: enqueued.append("dispatch") or True,
    )
    response = _post_warmup_session(app_client, account.id, strategy.id)

    assert response.status_code == 201
    assert enqueued == ["dispatch"]


def test_patch_disabled_actions_endpoint_persists_actions_and_returns_detail(
    app_client, db_session
) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    strategy.daily_action_limits_json = {"1": {"feed_read": 1, "react_to_post": 1}}
    created = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    db_session.commit()

    response = app_client.patch(
        f"/api/warmup/sessions/{created.id}/disabled-actions",
        json={"actions": ["react_to_post"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["disabled_actions"] == ["react_to_post"]
    db_session.refresh(created)
    assert created.disabled_actions_json == ["react_to_post"]
    assert (
        db_session.query(WarmupEvent).filter_by(event_type="disabled_actions_updated").count() == 1
    )


def test_patch_disabled_actions_alias_rejects_disabling_all_planned_actions(
    app_client, db_session
) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    strategy.daily_action_limits_json = {"1": {"feed_read": 1}}
    created = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    db_session.commit()

    response = app_client.patch(
        f"/api/warmup-sessions/{created.id}/disabled-actions",
        json={"actions": ["feed_read"]},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "WARMUP_SESSION_REJECTED"


def _seed_ready_account(db_session):
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


def _seed_shadow_strategy(db_session) -> WarmupStrategy:
    strategy = WarmupStrategy(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        name=f"Shadow {new_id()[:6]}",
        description="Shadow",
        tier_limits_json={},
        target_channels_json=[],
        is_preset=False,
        execution_mode=WarmupExecutionMode.SHADOW.value,
        preset_kind=WarmupPresetKind.STANDARD.value,
        duration_days=7,
        daily_action_limits_json={"1": {"feed_read": 1}},
    )
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _post_warmup_session(app_client, account_id: str, strategy_id: str):
    return app_client.post(
        "/api/warmup/sessions",
        json={"account_id": account_id, "strategy_id": strategy_id},
    )


def _create_session(db_session, account_id: str, strategy_id: str) -> WarmupSession:
    warmup_session = create_warmup_session(
        db_session,
        account_id=account_id,
        strategy_id=strategy_id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    db_session.commit()
    return warmup_session
