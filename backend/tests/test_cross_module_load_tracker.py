from __future__ import annotations

from datetime import UTC, datetime, timedelta

from freezegun import freeze_time
from sqlalchemy import select

from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    CrossModuleLoadBucket,
    new_id,
)
from app.services.cross_module_load_tracker import (
    current_load,
    evaluate_threshold,
    track,
)
from app.services.workspaces import ensure_default_workspace
from tests.helpers.factories import seed_account, seed_two_workspaces


_FROZEN_NOW = datetime(2026, 5, 20, 14, 37, 0, tzinfo=UTC)


@freeze_time(_FROZEN_NOW)
def test_warmup_only_under_conservative_threshold_is_ok(db_session) -> None:
    account = seed_account(db_session)

    track(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_id=account.id,
        module="warmup",
        count=5,
    )

    load = current_load(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_id=account.id,
    )
    assert load.last_hour == 5
    assert load.breakdown["warmup"] == 5
    assert evaluate_threshold(load, "conservative") == "ok"


@freeze_time(_FROZEN_NOW)
def test_combined_warmup_and_commenting_blocks_balanced_mode(db_session) -> None:
    account = seed_account(db_session)

    track(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_id=account.id,
        module="warmup",
        count=10,
    )
    track(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_id=account.id,
        module="commenting",
        count=20,
    )

    load = current_load(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_id=account.id,
    )
    assert load.last_hour == 30
    assert load.breakdown["commenting"] == 20
    assert evaluate_threshold(load, "balanced") == "blocked"


@freeze_time(_FROZEN_NOW)
def test_last_24h_excludes_bucket_25_hours_ago(db_session) -> None:
    account = seed_account(db_session)
    bucket_start = _FROZEN_NOW.replace(minute=0, second=0, microsecond=0)
    db_session.add(
        CrossModuleLoadBucket(
            id=new_id(),
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            account_id=account.id,
            bucket_start=bucket_start - timedelta(hours=25),
            warmup_actions=40,
        )
    )
    db_session.commit()

    track(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_id=account.id,
        module="other",
        count=3,
    )

    load = current_load(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_id=account.id,
    )
    assert load.last_hour == 3
    assert load.last_24h == 3
    assert load.breakdown["warmup"] == 0


@freeze_time(_FROZEN_NOW)
def test_tenant_isolation_hides_other_workspace_bucket(db_session) -> None:
    workspace_a, workspace_b = seed_two_workspaces(db_session)
    account = seed_account(db_session, workspace_id=workspace_a)

    track(
        db_session,
        workspace_id=workspace_a,
        account_id=account.id,
        module="editing",
        count=7,
    )

    load = current_load(db_session, workspace_id=workspace_b, account_id=account.id)
    assert load.last_hour == 0
    assert load.last_24h == 0
    assert load.breakdown["editing"] == 0


@freeze_time(_FROZEN_NOW)
def test_upsert_repeated_tracks_accumulate_one_current_bucket(db_session) -> None:
    ensure_default_workspace(db_session)
    account = seed_account(db_session)

    for _ in range(5):
        track(
            db_session,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            account_id=account.id,
            module="warmup",
        )

    bucket = db_session.execute(
        select(CrossModuleLoadBucket)
        .where(CrossModuleLoadBucket.workspace_id == DEFAULT_LOCAL_WORKSPACE_ID)
        .where(CrossModuleLoadBucket.account_id == account.id)
    ).scalar_one()
    assert bucket.warmup_actions == 5
    assert bucket.total_actions == 5
