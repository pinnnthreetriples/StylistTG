"""Data-driven role/auth matrix test for all API endpoints.

Adding coverage for a new endpoint requires only appending one tuple to
ENDPOINT_MATRIX.

Each entry is:
    (method, path, min_role, is_mutation)

``min_role`` is the lowest role that should be allowed access:
    "viewer"   → viewer, operator, admin, owner
    "operator" → operator, admin, owner
    "admin"    → admin, owner
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import Base
from app.main import app
from app.models import DEFAULT_LOCAL_USER_ID, DEFAULT_LOCAL_WORKSPACE_ID
from app.services.auth_context import AuthContext, get_current_auth_context
from app.services.database import create_sqlite_test_session_factory
from app.services.workspaces import ensure_default_workspace

from conftest import override_app_session

pytestmark = [pytest.mark.security, pytest.mark.api]


# ---------------------------------------------------------------------------
# Matrix definition
# ---------------------------------------------------------------------------

ENDPOINT_MATRIX: list[tuple[str, str, str, bool]] = [
    # (method, path, min_role, is_mutation)
    # Accounts
    ("GET", "/api/accounts", "viewer", False),
    ("POST", "/api/accounts", "operator", True),
    # Me
    ("GET", "/api/me", "viewer", False),
    # Diagnostics
    ("GET", "/diagnostics/runtime", "admin", False),
    ("GET", "/diagnostics/live-preflight", "admin", False),
    # Workers
    ("GET", "/api/workers/diagnostics", "admin", False),
    # Settings
    ("GET", "/api/settings/execution-policy", "viewer", False),
    ("PATCH", "/api/settings/execution-policy", "admin", True),
    # Auth runtime mode
    ("GET", "/api/auth/runtime-mode", "viewer", False),
    ("PATCH", "/api/auth/runtime-mode", "admin", True),
    # Import batches
    ("GET", "/api/account-import-batches", "viewer", False),
    ("POST", "/api/account-import-batches", "operator", True),
    # Auth batches
    ("GET", "/api/auth-batches", "viewer", False),
    ("POST", "/api/auth-batches", "operator", True),
    # Story drafts
    ("GET", "/api/story-drafts/{account_id}", "viewer", False),
    ("POST", "/api/story-drafts", "operator", True),
]

ROLE_ORDER = {"viewer": 0, "operator": 1, "admin": 2, "owner": 3}
ALL_ROLES = ["viewer", "operator", "admin", "owner"]


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _setup_test_env(*, role: str):
    """Create an isolated SQLite environment with a workspace member of *role*."""
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        _user, _workspace, member = ensure_default_workspace(session)
        member.role = role
        session.commit()

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id=DEFAULT_LOCAL_USER_ID,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role=role,
        auth_source="test",
    )
    return session_factory


def _resolve_path(path: str, ids: dict[str, str] | None = None) -> str:
    """Replace {account_id} etc. with real or dummy IDs."""
    if "{account_id}" in path:
        account_id = (ids or {}).get("account", "00000000-0000-4000-8000-000000000001")
        return path.replace("{account_id}", account_id)
    return path


def _request(client: TestClient, method: str, path: str):
    """Issue a request; for mutations send minimal valid-looking JSON."""
    if method == "GET":
        return client.get(path)
    if method == "POST":
        return client.post(path, json={})
    if method == "PATCH":
        return client.patch(path, json={})
    if method == "DELETE":
        return client.delete(path)
    if method == "PUT":
        return client.put(path, json={})
    raise ValueError(f"unsupported method {method}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.security
class TestNoAuth:
    """Unauthenticated requests must be rejected."""

    @pytest.mark.parametrize("method,path,min_role,is_mutation", ENDPOINT_MATRIX)
    def test_no_auth_returns_401_or_403(self, method, path, min_role, is_mutation, monkeypatch):
        monkeypatch.setattr("app.services.auth_context.settings.auth_mode", "supabase_jwt")
        app.dependency_overrides.clear()
        client = TestClient(app, raise_server_exceptions=False)
        try:
            resolved = _resolve_path(path)
            response = _request(client, method, resolved)
            assert response.status_code in {401, 403}, (
                f"{method} {path} returned {response.status_code} without auth"
            )
        finally:
            app.dependency_overrides.clear()


@pytest.mark.security
class TestViewerCannotMutate:
    """Viewer must not be able to perform mutations."""

    @pytest.mark.parametrize(
        "method,path,min_role,is_mutation",
        [(m, p, r, mut) for m, p, r, mut in ENDPOINT_MATRIX if mut and ROLE_ORDER[r] > ROLE_ORDER["viewer"]],
        ids=lambda val: f"{val}" if isinstance(val, str) else None,
    )
    def test_viewer_mutation_rejected(self, method, path, min_role, is_mutation):
        _setup_test_env(role="viewer")
        client = TestClient(app, raise_server_exceptions=False)
        try:
            resolved = _resolve_path(path)
            response = _request(client, method, resolved)
            assert response.status_code == 403, (
                f"viewer {method} {path} returned {response.status_code}, expected 403"
            )
        finally:
            app.dependency_overrides.clear()


@pytest.mark.security
class TestViewerReadAccess:
    """Viewer should be able to read viewer-accessible endpoints."""

    @pytest.mark.parametrize(
        "method,path,min_role,is_mutation",
        [(m, p, r, mut) for m, p, r, mut in ENDPOINT_MATRIX if not mut and r == "viewer"],
        ids=lambda val: f"{val}" if isinstance(val, str) else None,
    )
    def test_viewer_read_allowed(self, method, path, min_role, is_mutation):
        _setup_test_env(role="viewer")
        client = TestClient(app, raise_server_exceptions=False)
        try:
            resolved = _resolve_path(path)
            response = _request(client, method, resolved)
            assert response.status_code in {200, 404}, (
                f"viewer {method} {path} returned {response.status_code}, expected 200/404"
            )
        finally:
            app.dependency_overrides.clear()


@pytest.mark.security
class TestOperatorAdminEndpoints:
    """Operator must not access admin-only endpoints."""

    @pytest.mark.parametrize(
        "method,path,min_role,is_mutation",
        [(m, p, r, mut) for m, p, r, mut in ENDPOINT_MATRIX if r == "admin"],
        ids=lambda val: f"{val}" if isinstance(val, str) else None,
    )
    def test_operator_admin_endpoint_rejected(self, method, path, min_role, is_mutation):
        _setup_test_env(role="operator")
        client = TestClient(app, raise_server_exceptions=False)
        try:
            resolved = _resolve_path(path)
            response = _request(client, method, resolved)
            assert response.status_code == 403, (
                f"operator {method} {path} returned {response.status_code}, expected 403"
            )
        finally:
            app.dependency_overrides.clear()


@pytest.mark.security
class TestAdminAccess:
    """Admin can access admin-only read endpoints."""

    @pytest.mark.parametrize(
        "method,path,min_role,is_mutation",
        [(m, p, r, mut) for m, p, r, mut in ENDPOINT_MATRIX if r == "admin" and not mut],
        ids=lambda val: f"{val}" if isinstance(val, str) else None,
    )
    def test_admin_read_allowed(self, method, path, min_role, is_mutation):
        _setup_test_env(role="admin")
        client = TestClient(app, raise_server_exceptions=False)
        try:
            resolved = _resolve_path(path)
            response = _request(client, method, resolved)
            assert response.status_code == 200, (
                f"admin {method} {path} returned {response.status_code}, expected 200"
            )
        finally:
            app.dependency_overrides.clear()
