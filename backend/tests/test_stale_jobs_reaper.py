from datetime import timedelta

from app.models import JobState, utc_now
from app.services.accounts import create_account
from app.services.jobs import create_profile_job
from app.services.stale_jobs import reap_stale_jobs


def test_reap_stale_running_jobs_marks_failed_and_uncertain(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = "execution_usable"
    account.runtime_state.lock_owner = "worker:dead"
    account.runtime_state.lock_epoch = 1
    account.runtime_state.updated_at = utc_now() - timedelta(minutes=10)
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
        config=type("Config", (), {"profile_job_cooldown_seconds": 0})(),
    )
    job.job_state = JobState.RUNNING
    job.started_at = utc_now() - timedelta(minutes=10)
    db_session.commit()

    reaped = reap_stale_jobs(db_session, stale_after_seconds=300)

    db_session.refresh(job)
    db_session.refresh(account)
    assert reaped == 1
    assert job.job_state == JobState.FAILED
    assert job.failure_reason == "worker_timeout"
    assert account.runtime_state.lock_owner is None


def test_reap_stale_jobs_leaves_recent_running_job_alone(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = "execution_usable"
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
        config=type("Config", (), {"profile_job_cooldown_seconds": 0})(),
    )
    job.job_state = JobState.RUNNING
    job.started_at = utc_now()
    db_session.commit()

    assert reap_stale_jobs(db_session, stale_after_seconds=300) == 0
    assert job.job_state == JobState.RUNNING


def test_reap_stale_queued_jobs_uses_queued_at(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = "execution_usable"
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
        config=type("Config", (), {"profile_job_cooldown_seconds": 0})(),
    )
    job.job_state = JobState.QUEUED
    job.started_at = None
    job.queued_at = utc_now() - timedelta(minutes=10)
    db_session.commit()

    assert reap_stale_jobs(db_session, stale_after_seconds=300) == 1
    assert job.job_state == JobState.FAILED
    assert job.failure_reason == "worker_timeout"


def test_reap_stale_waiting_lock_jobs_uses_queued_at(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = "execution_usable"
    account.runtime_state.lock_owner = "worker:dead"
    account.runtime_state.updated_at = utc_now() - timedelta(minutes=10)
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
        config=type("Config", (), {"profile_job_cooldown_seconds": 0})(),
    )
    job.job_state = JobState.WAITING_LOCK
    job.started_at = None
    job.queued_at = utc_now() - timedelta(minutes=10)
    db_session.commit()

    assert reap_stale_jobs(db_session, stale_after_seconds=300) == 1
    assert job.job_state == JobState.FAILED
    assert account.runtime_state.lock_owner is None


def test_reap_stale_jobs_handles_naive_runtime_timestamp(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = "execution_usable"
    account.runtime_state.lock_owner = "worker:dead"
    account.runtime_state.updated_at = (utc_now() - timedelta(minutes=10)).replace(tzinfo=None)
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
        config=type("Config", (), {"profile_job_cooldown_seconds": 0})(),
    )
    job.job_state = JobState.WAITING_LOCK
    job.started_at = None
    job.queued_at = utc_now() - timedelta(minutes=10)
    db_session.commit()

    assert reap_stale_jobs(db_session, stale_after_seconds=300) == 1
    assert job.job_state == JobState.FAILED
    assert account.runtime_state.lock_owner is None


def test_reap_stale_jobs_leaves_partially_completed_job_alone(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = "execution_usable"
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
        config=type("Config", (), {"profile_job_cooldown_seconds": 0})(),
    )
    job.job_state = JobState.PARTIALLY_COMPLETED
    job.started_at = utc_now() - timedelta(minutes=10)
    job.finished_at = utc_now() - timedelta(minutes=9)
    db_session.commit()

    assert reap_stale_jobs(db_session, stale_after_seconds=300) == 0
    assert job.job_state == JobState.PARTIALLY_COMPLETED
