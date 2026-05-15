from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from redis.exceptions import RedisError

from app.job_queue import rq as rq_queue
from app.models import JobState, utc_now
from app.services.accounts import create_account
from app.services.jobs import create_profile_job
from app.services.stale_jobs import reconcile_orphaned_queued_jobs
from app.workers import profile_jobs

from conftest import FakeExecutionUsableAdapter

pytestmark = pytest.mark.unit


def _make_profile_job(db_session, *, external_ref: str = "+15550102000"):
    account = create_account(db_session, external_ref=external_ref)
    account.account_state = "execution_usable"
    db_session.commit()
    return create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
        execution_adapter=FakeExecutionUsableAdapter(),
    )


def _make_queued_job(db_session, *, age_minutes: int = 5):
    job = _make_profile_job(db_session)
    job.job_state = JobState.QUEUED
    job.queued_at = utc_now() - timedelta(minutes=age_minutes)
    db_session.commit()
    return job


def _make_lock_contended_job(db_session, *, age_seconds: int | None = None):
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
    if age_seconds is not None:
        job.queued_at = utc_now() - timedelta(seconds=age_seconds)
        db_session.commit()
    return job


def test_lock_contention_sets_waiting_lock_and_retries(db_session, monkeypatch) -> None:
    job = _make_lock_contended_job(db_session)
    reenqueue_calls: list[tuple[str, int, str | None]] = []

    def fake_reenqueue(
        job_id: str, *, delay_seconds: int, workflow_type: str | None = None
    ) -> bool:
        reenqueue_calls.append((job_id, delay_seconds, workflow_type))
        return True

    monkeypatch.setattr("app.job_queue.rq.reenqueue_job_with_delay", fake_reenqueue)

    exit_code = profile_jobs.execute_profile_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code == 1
    assert job.job_state == JobState.WAITING_LOCK
    assert reenqueue_calls == [(job.id, 5, "profile_update")]


def test_lock_contention_timeout_fails_job(db_session, monkeypatch) -> None:
    job = _make_lock_contended_job(db_session, age_seconds=120)
    monkeypatch.setattr(profile_jobs.settings, "max_lock_wait_seconds", 60)

    exit_code = profile_jobs.execute_profile_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code == 1
    assert job.job_state == JobState.FAILED
    assert job.failure_reason == "lock_wait_timeout"


def test_lock_contention_reenqueue_failure_does_not_crash(db_session, monkeypatch) -> None:
    job = _make_lock_contended_job(db_session)

    def failing_reenqueue(
        job_id: str, *, delay_seconds: int, workflow_type: str | None = None
    ) -> bool:
        raise RuntimeError("Redis down")

    monkeypatch.setattr("app.job_queue.rq.reenqueue_job_with_delay", failing_reenqueue)

    exit_code = profile_jobs.execute_profile_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code == 1
    assert job.job_state == JobState.WAITING_LOCK


def test_reconcile_orphaned_queued_job_fails_when_reenqueue_fails(db_session) -> None:
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


def test_reconcile_orphaned_queued_job_stays_queued_when_reenqueue_succeeds(db_session) -> None:
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


def test_reconcile_skips_already_enqueued_job(db_session) -> None:
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

    with patch("app.services.stale_jobs._default_is_enqueued", return_value=True) as mock_check:
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


class FakeQueue:
    name = "profile_jobs"
    connection = object()

    def __init__(self, *, fail_enqueue: bool = False) -> None:
        self.fail_enqueue = fail_enqueue
        self.enqueue_calls: list[tuple[timedelta, object, tuple[str], str]] = []

    def enqueue_in(self, delay: timedelta, func, *args: str, job_id: str):
        if self.fail_enqueue:
            raise RedisError("Redis down")
        self.enqueue_calls.append((delay, func, args, job_id))
        return object()


def test_reenqueue_job_with_delay_uses_retry_job_id(monkeypatch) -> None:
    queue = FakeQueue()
    monkeypatch.setattr(rq_queue, "get_profile_queue", lambda: queue)
    monkeypatch.setattr(rq_queue, "_cancel_existing_job", lambda *_: None)

    assert rq_queue.reenqueue_job_with_delay("job-1", delay_seconds=7) is True

    assert queue.enqueue_calls == [
        (timedelta(seconds=7), rq_queue.run_profile_job, ("job-1",), "retry-job-1")
    ]


def test_reenqueue_job_with_delay_cancels_existing_retry_before_enqueue(monkeypatch) -> None:
    events: list[str] = []
    queue = FakeQueue()

    class ExistingJob:
        def delete(self) -> None:
            events.append("delete")

    def fetch_job(job_id: str, *, connection) -> ExistingJob:
        assert job_id == "retry-job-1"
        assert connection is queue.connection
        return ExistingJob()

    def enqueue_in(delay: timedelta, func, *args: str, job_id: str):
        events.append("enqueue")
        queue.enqueue_calls.append((delay, func, args, job_id))
        return object()

    queue.enqueue_in = enqueue_in
    monkeypatch.setattr(rq_queue, "get_profile_queue", lambda: queue)
    monkeypatch.setattr(rq_queue.Job, "fetch", staticmethod(fetch_job))

    assert rq_queue.reenqueue_job_with_delay("job-1", delay_seconds=3) is True

    assert events == ["delete", "enqueue"]
    assert queue.enqueue_calls[0][3] == "retry-job-1"


def test_reenqueue_job_with_delay_account_update_uses_workflow_registry(monkeypatch) -> None:
    queue = FakeQueue()
    queue_names: list[str] = []
    handler_paths: list[str] = []

    def workflow_handler(job_id: str) -> None:
        return None

    def get_queue(queue_name: str) -> FakeQueue:
        queue_names.append(queue_name)
        return queue

    def resolve_handler(handler_path: str):
        handler_paths.append(handler_path)
        return workflow_handler

    monkeypatch.setattr("app.job_queue.workflows.get_queue", get_queue)
    monkeypatch.setattr("app.job_queue.workflows.resolve_handler", resolve_handler)
    monkeypatch.setattr("app.job_queue.workflows._cancel_existing_job", lambda *_: None)

    assert (
        rq_queue.reenqueue_job_with_delay("job-1", delay_seconds=30, workflow_type="account_update")
        is True
    )

    assert queue_names == [rq_queue.PROFILE_QUEUE_NAME]
    assert handler_paths == ["app.modules.account_editing.jobs:run_account_update_job"]
    assert queue.enqueue_calls == [
        (timedelta(seconds=30), workflow_handler, ("job-1",), "retry-job-1")
    ]


def test_reenqueue_job_with_delay_normal_workflow_selects_profile_worker(monkeypatch) -> None:
    queue = FakeQueue()
    monkeypatch.setattr(rq_queue, "get_profile_queue", lambda: queue)
    monkeypatch.setattr(rq_queue, "_cancel_existing_job", lambda *_: None)

    assert rq_queue.reenqueue_job_with_delay("job-1", delay_seconds=1) is True

    assert queue.enqueue_calls[0][1] is rq_queue.run_profile_job


def test_reenqueue_job_with_delay_returns_false_on_redis_error(monkeypatch) -> None:
    queue = FakeQueue(fail_enqueue=True)
    monkeypatch.setattr(rq_queue, "get_profile_queue", lambda: queue)
    monkeypatch.setattr(rq_queue, "_cancel_existing_job", lambda *_: None)

    assert rq_queue.reenqueue_job_with_delay("job-1", delay_seconds=1) is False
