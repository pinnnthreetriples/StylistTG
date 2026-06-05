from datetime import UTC, datetime, timedelta

from freezegun import freeze_time

from app.models import DEFAULT_LOCAL_WORKSPACE_ID, WarmupStatus
from app.services.warmup import create_warmup_session
from tests.helpers.warmup import seed_warmup_account, seed_warmup_strategy


@freeze_time("2026-06-05 10:30:00")
def test_warmup_session_timer_running(app_client, db_session) -> None:
    started_at = datetime(2026, 6, 5, 10, 0, tzinfo=UTC)
    warmup_session = _seed_session(db_session, started_at=started_at)
    warmup_session.status = WarmupStatus.ACTIVE.value
    warmup_session.started_at = started_at
    warmup_session.cycle_config_json = {
        "started_at": started_at.isoformat(),
        "active_hours_total": 1,
    }
    db_session.commit()

    response = app_client.get(f"/api/warmup-sessions/{warmup_session.id}/timer")

    assert response.status_code == 200
    body = response.json()
    assert body["started_at"] == "2026-06-05T10:00:00Z"
    assert body["total_duration_seconds"] == 3600
    assert body["elapsed_seconds"] == 1800
    assert body["status"] == "running"


@freeze_time("2026-06-05 10:30:00")
def test_warmup_session_timer_paused_freezes_elapsed(app_client, db_session) -> None:
    started_at = datetime(2026, 6, 5, 10, 0, tzinfo=UTC)
    warmup_session = _seed_session(db_session, started_at=started_at)
    warmup_session.status = WarmupStatus.PAUSED_MANUAL.value
    warmup_session.started_at = started_at
    warmup_session.paused_at = started_at + timedelta(minutes=10)
    warmup_session.cycle_config_json = {
        "started_at": started_at.isoformat(),
        "active_hours_total": 1,
    }
    db_session.commit()

    response = app_client.get(f"/api/warmup-sessions/{warmup_session.id}/timer")

    assert response.status_code == 200
    body = response.json()
    assert body["elapsed_seconds"] == 600
    assert body["status"] == "paused"


@freeze_time("2026-06-05 12:00:00")
def test_warmup_session_timer_completed_clamps_elapsed(app_client, db_session) -> None:
    started_at = datetime(2026, 6, 5, 10, 0, tzinfo=UTC)
    warmup_session = _seed_session(db_session, started_at=started_at)
    warmup_session.status = WarmupStatus.COMPLETED.value
    warmup_session.started_at = started_at
    warmup_session.completed_at = started_at + timedelta(hours=2)
    warmup_session.cycle_config_json = {
        "started_at": started_at.isoformat(),
        "active_hours_total": 1,
    }
    db_session.commit()

    response = app_client.get(f"/api/warmup-sessions/{warmup_session.id}/timer")

    assert response.status_code == 200
    body = response.json()
    assert body["total_duration_seconds"] == 3600
    assert body["elapsed_seconds"] == 3600
    assert body["status"] == "completed"


def _seed_session(db_session, *, started_at: datetime):
    account = seed_warmup_account(db_session)
    strategy = seed_warmup_strategy(db_session)
    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        now=started_at,
    )
    db_session.commit()
    return warmup_session
