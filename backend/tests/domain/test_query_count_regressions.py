"""Strict query-count ceiling regression tests.

Query-count ceilings lock in the optimizations from PRs 1-5.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from freezegun import freeze_time

from app.models import JobState

from tests.helpers.app import app_client
from tests.helpers.factories import make_session, seed_account_with_profile, seed_auth_batch, seed_job
from tests.helpers.query_count import QueryCounter

pytestmark = pytest.mark.api


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session():
    return make_session()


def _setup_accounts(session, n: int) -> list[str]:
    ids: list[str] = []
    for i in range(n):
        account = seed_account_with_profile(
            session,
            index=i,
            external_ref=f"+1555088{7000 + i}",
        )
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
    with app_client(sf) as client:
        with QueryCounter(engine) as counter:
            response = client.get("/api/accounts")
        assert response.status_code == 200
        assert len(response.json()) == 20
        assert counter.count <= ACCOUNTS_LIST_CEILING, (
            f"/api/accounts exceeded ceiling: {counter.count} > {ACCOUNTS_LIST_CEILING}"
        )


def test_risk_summary_ceiling():
    """GET /api/accounts/risk-summary with 10 accounts must not exceed ceiling."""
    sf, engine = _make_session()
    with sf() as session:
        _setup_accounts(session, 10)
    with app_client(sf) as client:
        with QueryCounter(engine) as counter:
            response = client.get("/api/accounts/risk-summary")
        assert response.status_code == 200
        assert counter.count <= RISK_SUMMARY_CEILING, (
            f"/api/accounts/risk-summary exceeded ceiling: {counter.count} > {RISK_SUMMARY_CEILING}"
        )


def test_safety_summary_ceiling():
    """GET /api/accounts/safety-summary must scale sub-linearly."""
    sf, engine = _make_session()
    with sf() as session:
        n = 10
        _setup_accounts(session, n)
    with app_client(sf) as client:
        with QueryCounter(engine) as counter:
            response = client.get("/api/accounts/safety-summary")
        assert response.status_code == 200
        assert len(response.json()) == n
        per_account = counter.count / n
        assert per_account <= SAFETY_SUMMARY_PER_ACCOUNT_CEILING, (
            f"/api/accounts/safety-summary per-account cost too high: "
            f"{per_account:.1f} > {SAFETY_SUMMARY_PER_ACCOUNT_CEILING}"
        )


def test_auth_batch_detail_ceiling():
    """GET /api/auth-batches/{id} must not exceed ceiling."""
    sf, engine = _make_session()
    with sf() as session:
        account_ids = _setup_accounts(session, 1)
        batch, _item = seed_auth_batch(
            session,
            account_id=account_ids[0],
            idempotency_key="test-key-ceiling",
        )
        batch_id = batch.id
    with app_client(sf) as client:
        with QueryCounter(engine) as counter:
            response = client.get(f"/api/auth-batches/{batch_id}")
        assert response.status_code == 200
        assert counter.count <= AUTH_BATCH_DETAIL_CEILING, (
            f"/api/auth-batches/{{id}} exceeded ceiling: {counter.count} > {AUTH_BATCH_DETAIL_CEILING}"
        )


@freeze_time("2026-01-15 12:00:00")
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
    with app_client(sf) as client:
        with QueryCounter(engine) as counter:
            response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        assert counter.count <= JOB_DETAIL_CEILING, (
            f"/api/jobs/{{id}} exceeded ceiling: {counter.count} > {JOB_DETAIL_CEILING}"
        )
