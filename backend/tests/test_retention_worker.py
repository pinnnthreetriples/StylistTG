from __future__ import annotations

from datetime import UTC, datetime, timedelta

from freezegun import freeze_time
from sqlalchemy import select

from app.config import Settings
from app.models import (
    AccountQuarantine,
    AccountStatusObservation,
    CrossModuleLoadBucket,
    NeuroCommentEvent,
    SensitiveAuditEvent,
)
from app.modules.account_lifecycle.retention import run_retention_tick
from app.services.scheduler import RETENTION_TICK_SECONDS, scheduler_report
from tests.helpers.factories import seed_account

_FROZEN_NOW = datetime(2026, 5, 20, 10, 0, tzinfo=UTC)


def _ids(session, model) -> set[str]:
    return set(session.execute(select(model.id)).scalars())


def test_retention_settings_defaults() -> None:
    config = Settings(_env_file=None)

    assert config.safety_retention_days_default == 90
    assert config.safety_retention_days_observations == 30
    assert config.safety_retention_days_load_buckets == 14


def test_scheduler_report_registers_daily_retention_tick() -> None:
    report = scheduler_report(Settings(_env_file=None))

    assert report.planned_ticks["retention"] == RETENTION_TICK_SECONDS


@freeze_time(_FROZEN_NOW)
def test_retention_tick_deletes_old_events_and_keeps_younger_events(db_session) -> None:
    account = seed_account(db_session)
    old_event = NeuroCommentEvent(
        workspace_id=account.workspace_id,
        account_id=account.id,
        event_type="old_event",
        event_level="info",
        message="old event",
        data_json={},
        created_at=_FROZEN_NOW - timedelta(days=91),
    )
    young_event = NeuroCommentEvent(
        workspace_id=account.workspace_id,
        account_id=account.id,
        event_type="young_event",
        event_level="info",
        message="young event",
        data_json={},
        created_at=_FROZEN_NOW - timedelta(days=89),
    )
    db_session.add_all([old_event, young_event])
    db_session.commit()

    report = run_retention_tick(db_session, now=_FROZEN_NOW)
    db_session.commit()

    assert report.events_deleted == 1
    assert _ids(db_session, NeuroCommentEvent) == {young_event.id}


@freeze_time(_FROZEN_NOW)
def test_retention_tick_respects_limit_at_cutoff(db_session) -> None:
    account = seed_account(db_session)
    boundary_event = NeuroCommentEvent(
        workspace_id=account.workspace_id,
        account_id=account.id,
        event_type="boundary_event",
        event_level="info",
        message="boundary event",
        data_json={},
        created_at=_FROZEN_NOW - timedelta(days=90),
    )
    db_session.add(boundary_event)
    db_session.commit()

    report = run_retention_tick(db_session, now=_FROZEN_NOW)
    db_session.commit()

    assert report.events_deleted == 0
    assert _ids(db_session, NeuroCommentEvent) == {boundary_event.id}


@freeze_time(_FROZEN_NOW)
def test_retention_tick_does_not_delete_sensitive_audit_events(db_session) -> None:
    account = seed_account(db_session)
    audit_event = SensitiveAuditEvent(
        workspace_id=account.workspace_id,
        actor_user_id=None,
        action="workspace_safety_policy.updated",
        entity_type="workspace_safety_policy",
        entity_id=account.workspace_id,
        metadata_json={},
        created_at=_FROZEN_NOW - timedelta(days=900),
    )
    db_session.add(audit_event)
    db_session.commit()

    report = run_retention_tick(db_session, now=_FROZEN_NOW)
    db_session.commit()

    assert report.events_deleted == 0
    assert _ids(db_session, SensitiveAuditEvent) == {audit_event.id}


@freeze_time(_FROZEN_NOW)
def test_retention_tick_deletes_old_observations(db_session) -> None:
    account = seed_account(db_session)
    old_observation = AccountStatusObservation(
        workspace_id=account.workspace_id,
        account_id=account.id,
        observed_at=_FROZEN_NOW - timedelta(days=31),
        proxy_healthy=True,
        proxy_ip_hash=None,
        tdlib_authorized=True,
        device_model_hash=None,
        consecutive_failures=0,
        auto_action_taken="none",
        details_json={},
    )
    young_observation = AccountStatusObservation(
        workspace_id=account.workspace_id,
        account_id=account.id,
        observed_at=_FROZEN_NOW - timedelta(days=29),
        proxy_healthy=True,
        proxy_ip_hash=None,
        tdlib_authorized=True,
        device_model_hash=None,
        consecutive_failures=0,
        auto_action_taken="none",
        details_json={},
    )
    db_session.add_all([old_observation, young_observation])
    db_session.commit()

    report = run_retention_tick(db_session, now=_FROZEN_NOW)
    db_session.commit()

    assert report.observations_deleted == 1
    assert _ids(db_session, AccountStatusObservation) == {young_observation.id}


@freeze_time(_FROZEN_NOW)
def test_retention_tick_deletes_old_load_buckets(db_session) -> None:
    account = seed_account(db_session)
    old_bucket = CrossModuleLoadBucket(
        workspace_id=account.workspace_id,
        account_id=account.id,
        bucket_start=_FROZEN_NOW - timedelta(days=15),
        warmup_actions=1,
    )
    young_bucket = CrossModuleLoadBucket(
        workspace_id=account.workspace_id,
        account_id=account.id,
        bucket_start=_FROZEN_NOW - timedelta(days=13),
        warmup_actions=1,
    )
    db_session.add_all([old_bucket, young_bucket])
    db_session.commit()

    report = run_retention_tick(db_session, now=_FROZEN_NOW)
    db_session.commit()

    assert report.load_buckets_deleted == 1
    assert _ids(db_session, CrossModuleLoadBucket) == {young_bucket.id}


@freeze_time(_FROZEN_NOW)
def test_retention_tick_deletes_released_old_quarantine_and_keeps_active(db_session) -> None:
    account = seed_account(db_session)
    released_old = AccountQuarantine(
        workspace_id=account.workspace_id,
        account_id=account.id,
        reason="manual",
        started_at=_FROZEN_NOW - timedelta(days=400, hours=1),
        until=_FROZEN_NOW - timedelta(days=400),
        released_at=_FROZEN_NOW - timedelta(days=366),
        metadata_json={},
    )
    active_old = AccountQuarantine(
        workspace_id=account.workspace_id,
        account_id=account.id,
        reason="manual",
        started_at=_FROZEN_NOW - timedelta(days=400),
        until=_FROZEN_NOW + timedelta(days=1),
        released_at=None,
        metadata_json={},
    )
    db_session.add_all([released_old, active_old])
    db_session.commit()

    report = run_retention_tick(db_session, now=_FROZEN_NOW)
    db_session.commit()

    assert report.quarantines_archived == 1
    assert _ids(db_session, AccountQuarantine) == {active_old.id}


@freeze_time(_FROZEN_NOW)
def test_retention_tick_is_idempotent(db_session) -> None:
    account = seed_account(db_session)
    db_session.add(
        NeuroCommentEvent(
            workspace_id=account.workspace_id,
            account_id=account.id,
            event_type="old_event",
            event_level="info",
            message="old event",
            data_json={},
            created_at=_FROZEN_NOW - timedelta(days=91),
        )
    )
    db_session.commit()

    first_report = run_retention_tick(db_session, now=_FROZEN_NOW)
    db_session.commit()
    second_report = run_retention_tick(db_session, now=_FROZEN_NOW)
    db_session.commit()

    assert first_report.events_deleted == 1
    assert second_report.events_deleted == 0
    assert second_report.observations_deleted == 0
    assert second_report.load_buckets_deleted == 0
    assert second_report.quarantines_archived == 0
