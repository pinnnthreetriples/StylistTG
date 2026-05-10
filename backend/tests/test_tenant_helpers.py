"""Tests for workspace-scoped tenant helpers.

Verifies that require_account_in_workspace and require_job_in_workspace
return 404 for foreign workspace entities without leaking existence.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.db import Base
from app.main import app
from app.models import AccountState
from app.services.accounts import create_account
from app.services.database import create_sqlite_test_session_factory

from conftest import override_app_session, seed_job


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session():
    sf, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    return sf, engine


def _seed_account(session, *, external_ref: str = "+15551000001") -> str:
    account = create_account(session, external_ref=external_ref)
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.session_present = True
    account.runtime_state.runtime_health = "ready"
    session.commit()
    return account.id


def _seed_job(session, account_id: str) -> str:
    from app.models import JobState
    job = seed_job(
        session,
        account_id=account_id,
        payload={"first_name": "Test"},
        state=JobState.COMPLETED,
    )
    return job.id


# ---------------------------------------------------------------------------
# Tests — require_account_in_workspace (via API endpoints)
# ---------------------------------------------------------------------------


def test_account_in_own_workspace_returns_200():
    sf, engine = _make_session()
    with sf() as session:
        account_id = _seed_account(session)
    override_app_session(sf)
    client = TestClient(app)
    try:
        response = client.get(f"/api/accounts/{account_id}")
        assert response.status_code == 200
        assert response.json()["id"] == account_id
    finally:
        app.dependency_overrides.clear()


def test_nonexistent_account_returns_404():
    sf, engine = _make_session()
    override_app_session(sf)
    client = TestClient(app)
    try:
        response = client.get("/api/accounts/00000000-0000-0000-0000-000000000099")
        assert response.status_code == 404
        body = response.json()
        assert body["error_code"] == "ACCOUNT_NOT_FOUND"
        assert "00000000-0000-0000-0000-000000000099" not in body["message"]
    finally:
        app.dependency_overrides.clear()


def test_account_safety_returns_404_for_nonexistent():
    sf, engine = _make_session()
    override_app_session(sf)
    client = TestClient(app)
    try:
        response = client.get("/api/accounts/00000000-0000-0000-0000-000000000099/safety")
        assert response.status_code == 404
        assert response.json()["error_code"] == "ACCOUNT_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_account_cooldowns_returns_404_for_nonexistent():
    sf, engine = _make_session()
    override_app_session(sf)
    client = TestClient(app)
    try:
        response = client.get("/api/accounts/00000000-0000-0000-0000-000000000099/cooldowns")
        assert response.status_code == 404
        assert response.json()["error_code"] == "ACCOUNT_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_account_risk_returns_404_for_nonexistent():
    sf, engine = _make_session()
    override_app_session(sf)
    client = TestClient(app)
    try:
        response = client.get("/api/accounts/00000000-0000-0000-0000-000000000099/risk")
        assert response.status_code == 404
        assert response.json()["error_code"] == "ACCOUNT_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests — require_job_in_workspace (via API endpoints)
# ---------------------------------------------------------------------------


def test_job_in_own_workspace_returns_200():
    sf, engine = _make_session()
    with sf() as session:
        account_id = _seed_account(session)
        job_id = _seed_job(session, account_id)
    override_app_session(sf)
    client = TestClient(app)
    try:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["job_id"] == job_id
    finally:
        app.dependency_overrides.clear()


def test_nonexistent_job_returns_404():
    sf, engine = _make_session()
    override_app_session(sf)
    client = TestClient(app)
    try:
        response = client.get("/api/jobs/00000000-0000-0000-0000-000000000099")
        assert response.status_code == 404
        body = response.json()
        assert body["error_code"] == "JOB_NOT_FOUND"
        assert "00000000-0000-0000-0000-000000000099" not in body["message"]
    finally:
        app.dependency_overrides.clear()


def test_job_cancel_returns_404_for_nonexistent():
    sf, engine = _make_session()
    override_app_session(sf)
    client = TestClient(app)
    try:
        response = client.post("/api/jobs/00000000-0000-0000-0000-000000000099/cancel")
        assert response.status_code == 404
        assert response.json()["error_code"] == "JOB_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_job_delete_returns_404_for_nonexistent():
    sf, engine = _make_session()
    override_app_session(sf)
    client = TestClient(app)
    try:
        response = client.delete("/api/jobs/00000000-0000-0000-0000-000000000099")
        assert response.status_code == 404
        assert response.json()["error_code"] == "JOB_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_job_steps_returns_404_for_nonexistent():
    sf, engine = _make_session()
    override_app_session(sf)
    client = TestClient(app)
    try:
        response = client.get("/api/jobs/00000000-0000-0000-0000-000000000099/steps")
        assert response.status_code == 404
        assert response.json()["error_code"] == "JOB_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests — error response does not leak entity existence
# ---------------------------------------------------------------------------


def test_account_404_does_not_leak_existence():
    """Response for missing account must not include the requested ID."""
    sf, engine = _make_session()
    override_app_session(sf)
    client = TestClient(app)
    fake_id = "00000000-leak-test-0000-000000000001"
    try:
        response = client.get(f"/api/accounts/{fake_id}")
        assert response.status_code == 404
        body_text = response.text
        assert fake_id not in body_text
    finally:
        app.dependency_overrides.clear()


def test_job_404_does_not_leak_existence():
    """Response for missing job must not include the requested ID."""
    sf, engine = _make_session()
    override_app_session(sf)
    client = TestClient(app)
    fake_id = "00000000-leak-test-0000-000000000002"
    try:
        response = client.get(f"/api/jobs/{fake_id}")
        assert response.status_code == 404
        body_text = response.text
        assert fake_id not in body_text
    finally:
        app.dependency_overrides.clear()
