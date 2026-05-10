from datetime import timedelta
from unittest.mock import patch

from app.models import JobState, utc_now
from app.services.accounts import create_account
from app.services.jobs import create_profile_job
from app.services.stale_jobs import reconcile_orphaned_queued_jobs


def _make_queued_job(db_session, *, age_minutes: int = 5):
    account = create_account(db_session, external_ref="+15550102000")
    account.account_state = "execution_usable"
    db_session.commit()
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
        config=type("Config", (), {"profile_job_cooldown_seconds": 0})(),
    )
    job.job_state = JobState.QUEUED
    job.queued_at = utc_now() - timedelta(minutes=age_minutes)
    db_session.commit()
    return job


def test_reconcile_orphaned_queued_job_fails_when_not_enqueued(db_session) -> None:
    job = _make_queued_job(db_session)

    with patch("app.job_queue.rq.reenqueue_job_with_delay", return_value=False):
        reconciled = reconcile_orphaned_queued_jobs(
            db_session,
            min_age_seconds=60,
            is_enqueued=lambda _: False,
        )

    db_session.refresh(job)
    assert reconciled == 1
    assert job.job_state == JobState.FAILED
    assert job.failure_reason == "queue_lost"


def test_reconcile_reenqueues_when_possible(db_session) -> None:
    job = _make_queued_job(db_session)

    with patch("app.job_queue.rq.reenqueue_job_with_delay", return_value=True):
        reconciled = reconcile_orphaned_queued_jobs(
            db_session,
            min_age_seconds=60,
            is_enqueued=lambda _: False,
        )

    db_session.refresh(job)
    assert reconciled == 1
    assert job.job_state == JobState.QUEUED


def test_reconcile_skips_enqueued_job(db_session) -> None:
    job = _make_queued_job(db_session)

    reconciled = reconcile_orphaned_queued_jobs(
        db_session,
        min_age_seconds=60,
        is_enqueued=lambda _: True,
    )

    db_session.refresh(job)
    assert reconciled == 0
    assert job.job_state == JobState.QUEUED


def test_reconcile_uses_default_redis_check_when_no_callback(db_session) -> None:
    job = _make_queued_job(db_session)

    with (
        patch("app.services.stale_jobs._default_is_enqueued", return_value=True) as mock_check,
    ):
        reconciled = reconcile_orphaned_queued_jobs(
            db_session,
            min_age_seconds=60,
        )

    mock_check.assert_called_once_with(job.id)
    db_session.refresh(job)
    assert reconciled == 0
    assert job.job_state == JobState.QUEUED


def test_reconcile_default_check_falls_through_to_fail(db_session) -> None:
    job = _make_queued_job(db_session)

    with (
        patch("app.services.stale_jobs._default_is_enqueued", return_value=False),
        patch("app.job_queue.rq.reenqueue_job_with_delay", return_value=False),
    ):
        reconciled = reconcile_orphaned_queued_jobs(
            db_session,
            min_age_seconds=60,
        )

    db_session.refresh(job)
    assert reconciled == 1
    assert job.job_state == JobState.FAILED
    assert job.failure_reason == "queue_lost"


def test_reconcile_skips_recent_queued_job(db_session) -> None:
    job = _make_queued_job(db_session, age_minutes=0)

    reconciled = reconcile_orphaned_queued_jobs(
        db_session,
        min_age_seconds=60,
        is_enqueued=lambda _: False,
    )

    db_session.refresh(job)
    assert reconciled == 0
    assert job.job_state == JobState.QUEUED


def test_reconcile_returns_zero_when_no_orphans(db_session) -> None:
    assert reconcile_orphaned_queued_jobs(db_session, min_age_seconds=60) == 0
