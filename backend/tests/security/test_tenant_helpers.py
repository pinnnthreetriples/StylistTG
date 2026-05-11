"""Tests for workspace-scoped tenant helpers.

Verifies that require_account_in_workspace and require_job_in_workspace
return 404 for nonexistent entities without leaking the requested ID.
Cross-workspace isolation tests live in test_workspace_isolation_matrix.py.
"""

from __future__ import annotations

import pytest

from app.models import AccountState
from app.services.accounts import create_account

from conftest import seed_job
from tests.helpers.app import app_client
from tests.helpers.factories import make_session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_ID = "00000000-0000-0000-0000-000000000099"


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
# Tests — own workspace returns 200
# ---------------------------------------------------------------------------


def test_account_in_own_workspace_returns_200():
    sf, _engine = make_session()
    with sf() as session:
        account_id = _seed_account(session)
    with app_client(sf) as client:
        response = client.get(f"/api/accounts/{account_id}")
        assert response.status_code == 200
        assert response.json()["id"] == account_id


def test_job_in_own_workspace_returns_200():
    sf, _engine = make_session()
    with sf() as session:
        account_id = _seed_account(session)
        job_id = _seed_job(session, account_id)
    with app_client(sf) as client:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["job_id"] == job_id


# ---------------------------------------------------------------------------
# Tests — nonexistent entities return 404 (parametrized)
# ---------------------------------------------------------------------------

NONEXISTENT_ACCOUNT_ENDPOINTS = [
    ("GET", f"/api/accounts/{FAKE_ID}", "ACCOUNT_NOT_FOUND"),
    ("GET", f"/api/accounts/{FAKE_ID}/safety", "ACCOUNT_NOT_FOUND"),
    ("GET", f"/api/accounts/{FAKE_ID}/cooldowns", "ACCOUNT_NOT_FOUND"),
    ("GET", f"/api/accounts/{FAKE_ID}/risk", "ACCOUNT_NOT_FOUND"),
]

NONEXISTENT_JOB_ENDPOINTS = [
    ("GET", f"/api/jobs/{FAKE_ID}", "JOB_NOT_FOUND"),
    ("POST", f"/api/jobs/{FAKE_ID}/cancel", "JOB_NOT_FOUND"),
    ("DELETE", f"/api/jobs/{FAKE_ID}", "JOB_NOT_FOUND"),
    ("GET", f"/api/jobs/{FAKE_ID}/steps", "JOB_NOT_FOUND"),
]


@pytest.mark.parametrize(
    "method,path,expected_error_code",
    NONEXISTENT_ACCOUNT_ENDPOINTS + NONEXISTENT_JOB_ENDPOINTS,
    ids=lambda v: v if isinstance(v, str) and "/" in v else None,
)
def test_nonexistent_entity_returns_404(method, path, expected_error_code):
    sf, _engine = make_session()
    with app_client(sf) as client:
        response = getattr(client, method.lower())(path)
        assert response.status_code == 404
        body = response.json()
        assert body["error_code"] == expected_error_code
        assert FAKE_ID not in body.get("message", "")


# ---------------------------------------------------------------------------
# Tests — error response does not leak entity existence
# ---------------------------------------------------------------------------

LEAK_ID = "00000000-leak-test-0000-000000000001"


@pytest.mark.parametrize(
    "path",
    [f"/api/accounts/{LEAK_ID}", f"/api/jobs/{LEAK_ID}"],
    ids=["account", "job"],
)
def test_404_does_not_leak_requested_id(path):
    """Response for missing entity must not include the requested ID."""
    sf, _engine = make_session()
    with app_client(sf) as client:
        response = client.get(path)
        assert response.status_code == 404
        assert LEAK_ID not in response.text
