"""Foundation tests for query-count tooling.

These tests verify the QueryCounter helper works with the SQLite test engine
and establish baseline counts for hot-path endpoints WITHOUT enforcing
aggressive upper bounds.  Strict ceilings belong in PR 9.
"""

from __future__ import annotations

from datetime import UTC, datetime

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
    """Seed *n* accounts with profile/runtime state for realistic queries."""
    ids: list[str] = []
    for i in range(n):
        account = create_account(session, external_ref=f"+1555010{2000 + i}")
        # create_account already creates runtime_state — update it in place
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


def _setup_auth_batch(session, account_id: str) -> str:
    batch = AuthBatch(
        workspace_id=Account.__table__.columns["workspace_id"].default.arg,
        label="test-batch",
        status=AuthBatchStatus.RUNNING,
        total_count=1,
        idempotency_key="test-key-1",
    )
    session.add(batch)
    session.flush()
    item = AuthBatchItem(
        batch_id=batch.id,
        account_id=account_id,
        phone_number="+15550102000",
        position=0,
        status=AuthBatchItemStatus.QUEUED,
    )
    session.add(item)
    session.commit()
    return batch.id


# ---------------------------------------------------------------------------
# Tests — QueryCounter sanity
# ---------------------------------------------------------------------------


def test_query_counter_counts_service_calls():
    """QueryCounter captures queries when used with a session."""
    sf, engine = _make_session()
    with sf() as session:
        create_account(session, external_ref="+15550100001")

    with sf() as session:
        with QueryCounter(engine) as counter:
            session.execute(Account.__table__.select())
        assert counter.count > 0, "QueryCounter must capture at least one query"


def test_query_counter_resets_between_contexts():
    """Each QueryCounter context starts at zero."""
    sf, engine = _make_session()
    with sf() as session:
        create_account(session, external_ref="+15550100002")

    with sf() as session:
        with QueryCounter(engine) as c1:
            session.execute(Account.__table__.select())
        first = c1.count

        with QueryCounter(engine) as c2:
            session.execute(Account.__table__.select())
        assert c2.count == first
        assert c1.count == first  # c1 stopped counting


# ---------------------------------------------------------------------------
# Tests — GET /api/accounts (1 account)
# ---------------------------------------------------------------------------


def test_accounts_list_1_account_query_count():
    sf, engine = _make_session()
    with sf() as session:
        _setup_accounts(session, 1)

    override_app_session(sf)
    client = TestClient(app)
    try:
        with QueryCounter(engine) as counter:
            response = client.get("/api/accounts")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert counter.count > 0, "expected queries for 1-account list"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests — GET /api/accounts (5 accounts)
# ---------------------------------------------------------------------------


def test_accounts_list_5_accounts_query_count():
    sf, engine = _make_session()
    with sf() as session:
        _setup_accounts(session, 5)

    override_app_session(sf)
    client = TestClient(app)
    try:
        with QueryCounter(engine) as counter:
            response = client.get("/api/accounts")
        assert response.status_code == 200
        assert len(response.json()) == 5
        assert counter.count > 0, "expected queries for 5-account list"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests — GET /api/accounts (20 accounts) — growth check
# ---------------------------------------------------------------------------


def test_accounts_list_20_accounts_query_count():
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
        assert counter.count > 0, "expected queries for 20-account list"
    finally:
        app.dependency_overrides.clear()


def test_accounts_list_query_count_does_not_grow_linearly():
    """Query count for 1, 5, 20 accounts must not grow proportionally."""
    counts: dict[int, int] = {}
    for n in (1, 5, 20):
        sf, engine = _make_session()
        with sf() as session:
            _setup_accounts(session, n)
        override_app_session(sf)
        client = TestClient(app)
        try:
            with QueryCounter(engine) as counter:
                response = client.get("/api/accounts")
            assert response.status_code == 200
            assert len(response.json()) == n
            counts[n] = counter.count
        finally:
            app.dependency_overrides.clear()
    # With batch loading, 20 accounts should use same queries as 1 account
    # (constant number of batch queries, not N per-account queries).
    # Allow small variance but NOT 20x growth.
    assert counts[20] <= counts[1] * 3, (
        f"query count grew too fast: 1-acct={counts[1]}, 5-acct={counts[5]}, 20-acct={counts[20]}"
    )


# ---------------------------------------------------------------------------
# Tests — GET /api/auth-batches/{id}
# ---------------------------------------------------------------------------


def test_auth_batch_detail_query_count():
    sf, engine = _make_session()
    with sf() as session:
        account_ids = _setup_accounts(session, 1)
        batch_id = _setup_auth_batch(session, account_ids[0])

    override_app_session(sf)
    client = TestClient(app)
    try:
        with QueryCounter(engine) as counter:
            response = client.get(f"/api/auth-batches/{batch_id}")
        assert response.status_code == 200
        assert counter.count > 0, "expected queries for auth-batch detail"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests — GET /api/jobs/{id}
# ---------------------------------------------------------------------------


def test_job_detail_query_count():
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
        assert counter.count > 0, "expected queries for job detail"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests — GET /api/accounts/safety-summary — query count
# ---------------------------------------------------------------------------


def test_safety_summary_query_count_does_not_grow_linearly():
    """Query count for safety-summary must not grow proportionally with account count."""
    counts: dict[int, int] = {}
    for n in (1, 5, 10):
        sf, engine = _make_session()
        with sf() as session:
            _setup_accounts(session, n)
        override_app_session(sf)
        client = TestClient(app)
        try:
            with QueryCounter(engine) as counter:
                response = client.get("/api/accounts/safety-summary")
            assert response.status_code == 200
            assert len(response.json()) == n
            counts[n] = counter.count
        finally:
            app.dependency_overrides.clear()
    assert counts[10] <= counts[1] * 3, (
        f"safety-summary query count grew too fast: 1-acct={counts[1]}, 5-acct={counts[5]}, 10-acct={counts[10]}"
    )


# ---------------------------------------------------------------------------
# Tests — GET /api/accounts/risk-summary — query count
# ---------------------------------------------------------------------------


def test_risk_summary_query_count_does_not_grow_linearly():
    """Query count for risk-summary must not grow proportionally with account count."""
    counts: dict[int, int] = {}
    for n in (1, 5, 10):
        sf, engine = _make_session()
        with sf() as session:
            _setup_accounts(session, n)
        override_app_session(sf)
        client = TestClient(app)
        try:
            with QueryCounter(engine) as counter:
                response = client.get("/api/accounts/risk-summary")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == n
            counts[n] = counter.count
        finally:
            app.dependency_overrides.clear()
    assert counts[10] <= counts[1] * 3, (
        f"risk-summary query count grew too fast: 1-acct={counts[1]}, 5-acct={counts[5]}, 10-acct={counts[10]}"
    )
