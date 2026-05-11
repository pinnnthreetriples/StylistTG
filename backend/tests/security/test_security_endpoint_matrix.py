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

from contextlib import contextmanager

import pytest
from fastapi.routing import APIRoute
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

# Routes explicitly exempt from the RBAC matrix.  Auth coverage for these
# is verified separately in test_security_regressions.py.  When adding a
# new route, either add an ENDPOINT_MATRIX entry or append here with a
# comment explaining why RBAC parametrization is not applicable.
RBAC_EXEMPT: set[tuple[str, str]] = {
    # Health / infra (no auth required by design)
    ("GET", "/health"),
    ("GET", "/ready"),
    # Object-level endpoints — require real entity IDs, tested in
    # test_workspace_isolation_matrix / test_tenant_helpers / contract tests
    ("GET", "/api/accounts/{account_id}"),
    ("DELETE", "/api/accounts/{account_id}"),
    ("GET", "/api/accounts/{account_id}/safety"),
    ("POST", "/api/accounts/{account_id}/safety-overrides"),
    ("GET", "/api/accounts/{account_id}/cooldowns"),
    ("GET", "/api/accounts/{account_id}/risk"),
    ("GET", "/api/accounts/{account_id}/action-gate"),
    ("GET", "/api/accounts/{account_id}/auth-state"),
    ("GET", "/api/accounts/{account_id}/runtime-diagnostics"),
    ("POST", "/api/accounts/{account_id}/refresh-runtime"),
    ("GET", "/api/accounts/{account_id}/jobs"),
    ("GET", "/api/accounts/{account_id}/jobs/latest"),
    ("GET", "/api/accounts/{account_id}/operation-logs"),
    ("GET", "/api/accounts/{account_id}/audit-events"),
    ("GET", "/api/accounts/{account_id}/deletion-preview"),
    ("POST", "/api/accounts/{account_id}/deletion-requests"),
    ("GET", "/api/accounts/{account_id}/deletion-requests"),
    ("GET", "/api/accounts/{account_id}/deletion-requests/{request_id}"),
    ("POST", "/api/accounts/{account_id}/export-requests"),
    ("GET", "/api/accounts/{account_id}/export-requests"),
    ("GET", "/api/accounts/{account_id}/export-requests/{request_id}"),
    ("GET", "/api/accounts/{account_id}/proxy"),
    ("PUT", "/api/accounts/{account_id}/proxy"),
    ("DELETE", "/api/accounts/{account_id}/proxy"),
    ("POST", "/api/accounts/{account_id}/proxy/check"),
    ("POST", "/api/accounts/{account_id}/validity-check"),
    ("GET", "/api/accounts/{account_id}/validity-checks"),
    ("POST", "/api/accounts/{account_id}/reauth-sessions"),
    # Bulk / collection endpoints without path params
    ("GET", "/api/accounts/auth-state"),
    ("GET", "/api/accounts/jobs"),
    ("GET", "/api/accounts/jobs/latest"),
    ("GET", "/api/accounts/risk-summary"),
    ("GET", "/api/accounts/safety-summary"),
    ("POST", "/api/accounts/safety-batch-preview"),
    ("GET", "/api/accounts/proxy-summary"),
    ("GET", "/api/accounts/runtime-diagnostics"),
    ("POST", "/api/accounts/refresh-runtime"),
    ("POST", "/api/accounts/auth-sessions"),
    ("GET", "/api/accounts/auth-sessions"),
    ("GET", "/api/accounts/auth-sessions/{auth_session_id}"),
    ("POST", "/api/accounts/auth-sessions/{auth_session_id}/cancel"),
    ("POST", "/api/accounts/auth-sessions/{auth_session_id}/code"),
    ("POST", "/api/accounts/auth-sessions/{auth_session_id}/password"),
    # Account import sub-routes
    ("GET", "/api/account-import-batches/{batch_id}"),
    ("POST", "/api/account-import-batches/{batch_id}/validate"),
    ("POST", "/api/account-import-batches/{batch_id}/confirm"),
    # Account update
    ("POST", "/api/account-update/preview"),
    ("POST", "/api/account-update/jobs"),
    # Auth batches — sub-routes
    ("POST", "/api/auth-batches/validate-phones"),
    ("GET", "/api/auth-batches/{batch_id}"),
    ("POST", "/api/auth-batches/{batch_id}/start"),
    ("POST", "/api/auth-batches/{batch_id}/cancel"),
    ("POST", "/api/auth-batches/{batch_id}/pause"),
    ("POST", "/api/auth-batches/{batch_id}/resume"),
    ("GET", "/api/auth-batches/{batch_id}/poll"),
    ("GET", "/api/auth-batches/{batch_id}/events"),
    ("POST", "/api/auth-batches/{batch_id}/items/{item_id}/submit-code"),
    ("POST", "/api/auth-batches/{batch_id}/items/{item_id}/submit-2fa"),
    ("POST", "/api/auth-batches/{batch_id}/items/{item_id}/cancel"),
    ("POST", "/api/auth-batches/{batch_id}/items/{item_id}/retry"),
    ("POST", "/api/auth-batches/{batch_id}/items/{item_id}/request-new-code"),
    # Auth OTP/password — special auth flows, not role-gated
    ("POST", "/api/auth/otp/start"),
    ("POST", "/api/auth/otp/confirm"),
    ("POST", "/api/auth/password"),
    # Assets — workspace-scoped, tested in isolation matrix
    ("POST", "/api/assets/profile-photo"),
    ("POST", "/api/assets/profile-audio"),
    ("POST", "/api/assets/story-image"),
    ("POST", "/api/assets/story-video"),
    ("GET", "/api/assets/{asset_id}"),
    ("GET", "/api/assets/{asset_id}/content"),
    ("GET", "/api/assets/{asset_id}/signed-url"),
    # Dashboard
    ("GET", "/api/dashboard/profile"),
    ("GET", "/api/dashboard/profile/{account_id}"),
    # Jobs
    ("POST", "/api/jobs/profile"),
    ("POST", "/api/jobs/profile/preview"),
    ("GET", "/api/jobs/policies"),
    ("GET", "/api/jobs/{job_id}"),
    ("DELETE", "/api/jobs/{job_id}"),
    ("POST", "/api/jobs/{job_id}/cancel"),
    ("GET", "/api/jobs/{job_id}/steps"),
    # Audit / operation logs
    ("GET", "/api/audit/events"),
    ("GET", "/api/operation-logs"),
    # Story drafts — sub-routes
    ("GET", "/api/story-drafts"),
    ("PATCH", "/api/story-drafts/{draft_id}"),
    ("DELETE", "/api/story-drafts/{draft_id}"),
    # Story capabilities / posts
    ("GET", "/api/story-capabilities"),
    ("GET", "/api/story-capabilities/{account_id}"),
    ("DELETE", "/api/story-posts/{story_post_id}"),
    # TDLib runtime
    ("GET", "/api/tdlib/runtime"),
    # Warmup
    ("GET", "/api/warmup/readiness"),
    ("POST", "/api/warmup/validate"),
    ("GET", "/api/warmup/strategies"),
    ("POST", "/api/warmup/sessions"),
    ("GET", "/api/warmup/sessions"),
    ("GET", "/api/warmup/sessions/{session_id}"),
    ("DELETE", "/api/warmup/sessions/{session_id}"),
    ("GET", "/api/warmup/sessions/{session_id}/events"),
    ("GET", "/api/warmup/sessions/{session_id}/status"),
    ("PUT", "/api/warmup/sessions/{session_id}/pause"),
    ("PUT", "/api/warmup/sessions/{session_id}/resume"),
    ("GET", "/api/warmup/isolation/by-account/{account_id}"),
    # Workers — sub-routes
    ("GET", "/api/workers/job-policies"),
    ("GET", "/api/workers/queues"),
    # Diagnostics — sub-routes
    ("GET", "/diagnostics/frontend-summary"),
}


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@contextmanager
def _role_test_client(role: str):
    """Yield a TestClient for the given role and clean dependency_overrides on exit."""
    _setup_test_env(role=role)
    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


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
            # contract: unauthenticated requests must return either 401 (Unauthorized)
            # or 403 (Forbidden) — both are valid auth-failure responses.
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
        [
            (m, p, r, mut)
            for m, p, r, mut in ENDPOINT_MATRIX
            if mut and ROLE_ORDER[r] > ROLE_ORDER["viewer"]
        ],
        ids=lambda val: f"{val}" if isinstance(val, str) else None,
    )
    def test_viewer_mutation_rejected(self, method, path, min_role, is_mutation):
        with _role_test_client("viewer") as client:
            resolved = _resolve_path(path)
            response = _request(client, method, resolved)
            assert response.status_code == 403, (
                f"viewer {method} {path} returned {response.status_code}, expected 403"
            )
            assert response.json()


@pytest.mark.security
class TestViewerReadAccess:
    """Viewer should be able to read viewer-accessible endpoints."""

    @pytest.mark.parametrize(
        "method,path,min_role,is_mutation",
        [(m, p, r, mut) for m, p, r, mut in ENDPOINT_MATRIX if not mut and r == "viewer"],
        ids=lambda val: f"{val}" if isinstance(val, str) else None,
    )
    def test_viewer_read_allowed(self, method, path, min_role, is_mutation):
        with _role_test_client("viewer") as client:
            resolved = _resolve_path(path)
            response = _request(client, method, resolved)
            # contract: viewer reads return 200 if resource exists,
            # 404 if path parameter targets a non-existent fixture id.
            assert response.status_code in {200, 404}, (
                f"viewer {method} {path} returned {response.status_code}, expected 200/404"
            )


@pytest.mark.security
class TestOperatorAdminEndpoints:
    """Operator must not access admin-only endpoints."""

    @pytest.mark.parametrize(
        "method,path,min_role,is_mutation",
        [(m, p, r, mut) for m, p, r, mut in ENDPOINT_MATRIX if r == "admin"],
        ids=lambda val: f"{val}" if isinstance(val, str) else None,
    )
    def test_operator_admin_endpoint_rejected(self, method, path, min_role, is_mutation):
        with _role_test_client("operator") as client:
            resolved = _resolve_path(path)
            response = _request(client, method, resolved)
            assert response.status_code == 403, (
                f"operator {method} {path} returned {response.status_code}, expected 403"
            )
            assert response.json()


@pytest.mark.security
class TestAdminAccess:
    """Admin can access admin-only read endpoints."""

    @pytest.mark.parametrize(
        "method,path,min_role,is_mutation",
        [(m, p, r, mut) for m, p, r, mut in ENDPOINT_MATRIX if r == "admin" and not mut],
        ids=lambda val: f"{val}" if isinstance(val, str) else None,
    )
    def test_admin_read_allowed(self, method, path, min_role, is_mutation):
        with _role_test_client("admin") as client:
            resolved = _resolve_path(path)
            response = _request(client, method, resolved)
            assert response.status_code == 200, (
                f"admin {method} {path} returned {response.status_code}, expected 200"
            )


# ---------------------------------------------------------------------------
# RBAC coverage completeness
# ---------------------------------------------------------------------------


@pytest.mark.security
class TestRbacCoverageCompleteness:
    """Every APIRoute must be in ENDPOINT_MATRIX or RBAC_EXEMPT."""

    def test_all_routes_accounted_for(self):
        matrix_paths = {(m, p) for m, p, _r, _mut in ENDPOINT_MATRIX}
        known = matrix_paths | RBAC_EXEMPT

        missing: list[str] = []
        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue
            for method in sorted(route.methods or []):
                key = (method, route.path)
                if key not in known:
                    missing.append(f"{method} {route.path}")

        assert missing == [], (
            "Routes not covered by ENDPOINT_MATRIX or RBAC_EXEMPT — "
            "add each to one of the two lists:\n  " + "\n  ".join(sorted(missing))
        )
