"""PR 9: Strict query-count ceilings and worker reconciliation regression tests.

Query-count ceilings lock in the optimizations from PRs 1-5.
Worker reconciliation tests verify PRs 6a-6d safeguards.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.db import Base
from app.main import app
from app.models import (
    Account,
    AccountProfileState,
    AccountState,
    AuthBatch,
    AuthBatchItem,
    AuthBatchItemStatus,
    AuthBatchStatus,
    JobState,
)
from app.services.accounts import create_account
from app.services.database import create_sqlite_test_session_factory
from app.services.stale_jobs import reconcile_orphaned_queued_jobs

from conftest import override_app_session, seed_job
from tests.helpers.query_count import QueryCounter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session():
    sf, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    return sf, engine


def _setup_accounts(session, n: int) -> list[str]:
    ids: list[str] = []
    for i in range(n):
        account = create_account(session, external_ref=f"+1555088{7000 + i}")
        account.runtime_state.session_present = True
        account.runtime_state.runtime_health = "ready"
        account.account_state = AccountState.EXECUTION_USABLE
        session.add(
            AccountProfileState(
                account_id=account.id,
                telegram_user_id=f"tg-{i}",
                first_name=f"User{i}",
                last_name="Test",
                username=f"user{i}",
                bio="",
            )
        )
        session.commit()
        ids.append(account.id)
    return ids


# ---------------------------------------------------------------------------
# Strict query-count ceilings
# ---------------------------------------------------------------------------

# Baselines (measured after PR 1-5 optimizations on SQLite):
#   /api/accounts          — 7 queries (constant across 1..20 accounts)
#   /api/accounts/risk-summary   — 7 queries (constant)
#   /api/accounts/safety-summary — 14 for 1 account, 32 for 10
#   /api/auth-batches/{id}       — 6 queries
#   /api/jobs/{id}               — 6 queries

ACCOUNTS_LIST_CEILING = 10
RISK_SUMMARY_CEILING = 10
SAFETY_SUMMARY_PER_ACCOUNT_CEILING = 5
AUTH_BATCH_DETAIL_CEILING = 10
JOB_DETAIL_CEILING = 10


def test_accounts_list_ceiling():
    """GET /api/accounts with 20 accounts must not exceed ceiling."""
    sf, engine = _make_session()
    with sf() as session:
        _setup_accounts(session, 20)
    override_app_session(sf)
    client = TestClient(app)
    try:
        with QueryCounter(engine) as counter:
            response = client.get("/api/accounts")
        assert response.status_code == 200
        assert len(response.json()) == 20
        assert counter.count <= ACCOUNTS_LIST_CEILING, (
            f"/api/accounts exceeded ceiling: {counter.count} > {ACCOUNTS_LIST_CEILING}"
        )
    finally:
        app.dependency_overrides.clear()


def test_risk_summary_ceiling():
    """GET /api/accounts/risk-summary with 10 accounts must not exceed ceiling."""
    sf, engine = _make_session()
    with sf() as session:
        _setup_accounts(session, 10)
    override_app_session(sf)
    client = TestClient(app)
    try:
        with QueryCounter(engine) as counter:
            response = client.get("/api/accounts/risk-summary")
        assert response.status_code == 200
        assert counter.count <= RISK_SUMMARY_CEILING, (
            f"/api/accounts/risk-summary exceeded ceiling: {counter.count} > {RISK_SUMMARY_CEILING}"
        )
    finally:
        app.dependency_overrides.clear()


def test_safety_summary_ceiling():
    """GET /api/accounts/safety-summary must scale sub-linearly."""
    sf, engine = _make_session()
    with sf() as session:
        n = 10
        _setup_accounts(session, n)
    override_app_session(sf)
    client = TestClient(app)
    try:
        with QueryCounter(engine) as counter:
            response = client.get("/api/accounts/safety-summary")
        assert response.status_code == 200
        assert len(response.json()) == n
        per_account = counter.count / n
        assert per_account <= SAFETY_SUMMARY_PER_ACCOUNT_CEILING, (
            f"/api/accounts/safety-summary per-account cost too high: "
            f"{per_account:.1f} > {SAFETY_SUMMARY_PER_ACCOUNT_CEILING}"
        )
    finally:
        app.dependency_overrides.clear()


def test_auth_batch_detail_ceiling():
    """GET /api/auth-batches/{id} must not exceed ceiling."""
    sf, engine = _make_session()
    with sf() as session:
        account_ids = _setup_accounts(session, 1)
        batch = AuthBatch(
            workspace_id=Account.__table__.columns["workspace_id"].default.arg,
            label="test-batch",
            status=AuthBatchStatus.RUNNING,
            total_count=1,
            idempotency_key="test-key-ceiling",
        )
        session.add(batch)
        session.flush()
        session.add(AuthBatchItem(
            batch_id=batch.id,
            account_id=account_ids[0],
            phone_number="+15550102000",
            position=0,
            status=AuthBatchItemStatus.QUEUED,
        ))
        session.commit()
        batch_id = batch.id
    override_app_session(sf)
    client = TestClient(app)
    try:
        with QueryCounter(engine) as counter:
            response = client.get(f"/api/auth-batches/{batch_id}")
        assert response.status_code == 200
        assert counter.count <= AUTH_BATCH_DETAIL_CEILING, (
            f"/api/auth-batches/{{id}} exceeded ceiling: {counter.count} > {AUTH_BATCH_DETAIL_CEILING}"
        )
    finally:
        app.dependency_overrides.clear()


def test_job_detail_ceiling():
    """GET /api/jobs/{id} must not exceed ceiling."""
    sf, engine = _make_session()
    with sf() as session:
        account_ids = _setup_accounts(session, 1)
        job = seed_job(
            session,
            account_id=account_ids[0],
            payload={"first_name": "Changed"},
            state=JobState.COMPLETED,
            finished_at=datetime.now(UTC),
        )
        job_id = job.id
    override_app_session(sf)
    client = TestClient(app)
    try:
        with QueryCounter(engine) as counter:
            response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        assert counter.count <= JOB_DETAIL_CEILING, (
            f"/api/jobs/{{id}} exceeded ceiling: {counter.count} > {JOB_DETAIL_CEILING}"
        )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Worker reconciliation regression tests (PR 6a-6d safeguards)
# ---------------------------------------------------------------------------


def test_reconcile_orphaned_queued_job_is_failed(db_session) -> None:
    """An orphaned QUEUED job older than min_age is failed with queue_lost."""
    account = create_account(db_session, external_ref="+15550880001")
    job = seed_job(
        db_session,
        account_id=account.id,
        payload={"first_name": "Orphan"},
        state=JobState.QUEUED,
    )
    job.queued_at = datetime.now(UTC) - timedelta(seconds=120)
    db_session.commit()

    with patch("app.job_queue.rq.reenqueue_job_with_delay", return_value=False):
        count = reconcile_orphaned_queued_jobs(
            db_session,
            min_age_seconds=60,
            is_enqueued=lambda _: False,
        )

    assert count == 1
    db_session.refresh(job)
    assert job.job_state == JobState.FAILED
    assert job.failure_reason == "queue_lost"


def test_reconcile_skips_enqueued_jobs(db_session) -> None:
    """Jobs that are still enqueued in Redis should not be reconciled."""
    account = create_account(db_session, external_ref="+15550880002")
    job = seed_job(
        db_session,
        account_id=account.id,
        payload={"first_name": "Enqueued"},
        state=JobState.QUEUED,
    )
    job.queued_at = datetime.now(UTC) - timedelta(seconds=120)
    db_session.commit()

    count = reconcile_orphaned_queued_jobs(
        db_session,
        min_age_seconds=60,
        is_enqueued=lambda _: True,
    )

    assert count == 0
    db_session.refresh(job)
    assert job.job_state == JobState.QUEUED


def test_reconcile_skips_recent_jobs(db_session) -> None:
    """Jobs newer than min_age should not be reconciled."""
    account = create_account(db_session, external_ref="+15550880003")
    job = seed_job(
        db_session,
        account_id=account.id,
        payload={"first_name": "Recent"},
        state=JobState.QUEUED,
    )
    job.queued_at = datetime.now(UTC) - timedelta(seconds=10)
    db_session.commit()

    count = reconcile_orphaned_queued_jobs(
        db_session,
        min_age_seconds=60,
        is_enqueued=lambda _: False,
    )

    assert count == 0
    db_session.refresh(job)
    assert job.job_state == JobState.QUEUED


def test_reconcile_reenqueues_orphaned_job(db_session) -> None:
    """An orphaned job is re-enqueued successfully when reenqueue succeeds."""
    account = create_account(db_session, external_ref="+15550880004")
    job = seed_job(
        db_session,
        account_id=account.id,
        payload={"first_name": "Reenqueue"},
        state=JobState.QUEUED,
    )
    job.queued_at = datetime.now(UTC) - timedelta(seconds=120)
    db_session.commit()

    with patch("app.job_queue.rq.reenqueue_job_with_delay", return_value=True):
        count = reconcile_orphaned_queued_jobs(
            db_session,
            min_age_seconds=60,
            is_enqueued=lambda _: False,
        )

    assert count == 1
    db_session.refresh(job)
    assert job.job_state == JobState.QUEUED


def test_lock_wait_timeout_fails_job(db_session) -> None:
    """A job waiting for lock longer than max_lock_wait_seconds is failed."""
    from app.workers.profile_jobs import _handle_lock_contention

    account = create_account(db_session, external_ref="+15550880005")
    job = seed_job(
        db_session,
        account_id=account.id,
        payload={"first_name": "Timeout"},
        state=JobState.QUEUED,
    )
    job.queued_at = datetime.now(UTC) - timedelta(seconds=999)
    db_session.commit()

    with patch("app.config.settings.max_lock_wait_seconds", 60):
        result = _handle_lock_contention(db_session, job, job.id)

    assert result == 1
    db_session.refresh(job)
    assert job.job_state == JobState.FAILED
    assert job.failure_reason == "lock_wait_timeout"


def test_lock_retry_sets_waiting_lock_and_reenqueues(db_session) -> None:
    """A job within lock wait window is set to WAITING_LOCK and re-enqueued."""
    from app.workers.profile_jobs import _handle_lock_contention

    account = create_account(db_session, external_ref="+15550880006")
    job = seed_job(
        db_session,
        account_id=account.id,
        payload={"first_name": "Retry"},
        state=JobState.QUEUED,
    )
    job.queued_at = datetime.now(UTC) - timedelta(seconds=5)
    db_session.commit()

    with patch("app.config.settings.max_lock_wait_seconds", 60), \
         patch("app.workers.profile_jobs._try_reenqueue") as mock_reenqueue:
        result = _handle_lock_contention(db_session, job, job.id)

    assert result == 1
    db_session.refresh(job)
    assert job.job_state == JobState.WAITING_LOCK
    mock_reenqueue.assert_called_once()
