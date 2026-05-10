from datetime import timedelta

from app.models import JobState, utc_now
from app.services.accounts import create_account
from app.services.jobs import create_profile_job
from app.workers import profile_jobs

from conftest import FakeExecutionUsableAdapter


def test_lock_contention_sets_waiting_lock_and_retries(db_session, monkeypatch) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    account.account_state = "execution_usable"
    account.runtime_state.lock_owner = "worker:other:xyz"
    account.runtime_state.lock_epoch = 1
    account.runtime_state.updated_at = utc_now()
    db_session.commit()
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
        execution_adapter=FakeExecutionUsableAdapter(),
    )

    reenqueue_calls: list[tuple[str, int, str | None]] = []

    def fake_reenqueue(job_id: str, *, delay_seconds: int, workflow_type: str | None = None) -> bool:
        reenqueue_calls.append((job_id, delay_seconds, workflow_type))
        return True

    monkeypatch.setattr("app.job_queue.rq.reenqueue_job_with_delay", fake_reenqueue)

    exit_code = profile_jobs.execute_profile_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code == 1
    assert job.job_state == JobState.WAITING_LOCK
    assert len(reenqueue_calls) == 1
    assert reenqueue_calls[0][0] == job.id
    assert reenqueue_calls[0][1] == 5  # default lock_retry_delay_seconds


def test_lock_contention_timeout_fails_job(db_session, monkeypatch) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    account.account_state = "execution_usable"
    account.runtime_state.lock_owner = "worker:other:xyz"
    account.runtime_state.lock_epoch = 1
    account.runtime_state.updated_at = utc_now()
    db_session.commit()
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
        execution_adapter=FakeExecutionUsableAdapter(),
    )
    job.queued_at = utc_now() - timedelta(seconds=120)
    db_session.commit()

    monkeypatch.setattr(profile_jobs.settings, "max_lock_wait_seconds", 60)

    exit_code = profile_jobs.execute_profile_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code == 1
    assert job.job_state == JobState.FAILED
    assert job.failure_reason == "lock_wait_timeout"


def test_lock_contention_reenqueue_failure_does_not_crash(db_session, monkeypatch) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    account.account_state = "execution_usable"
    account.runtime_state.lock_owner = "worker:other:xyz"
    account.runtime_state.lock_epoch = 1
    account.runtime_state.updated_at = utc_now()
    db_session.commit()
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
        execution_adapter=FakeExecutionUsableAdapter(),
    )

    def failing_reenqueue(job_id: str, *, delay_seconds: int, workflow_type: str | None = None) -> bool:
        raise RuntimeError("Redis down")

    monkeypatch.setattr("app.job_queue.rq.reenqueue_job_with_delay", failing_reenqueue)

    exit_code = profile_jobs.execute_profile_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code == 1
    assert job.job_state == JobState.WAITING_LOCK
