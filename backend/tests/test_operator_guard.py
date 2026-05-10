from fastapi.testclient import TestClient

from app.config import settings
from app.db import Base
from app.main import app, _configured_cors_origins, _is_local_client
from app.models import User, Workspace, WorkspaceMember, WorkspacePlan
from app.services.database import create_sqlite_test_session_factory

from conftest import override_app_session
from tests.helpers.app import app_client
from tests.helpers.factories import make_session


class DummyClient:
    host = "203.0.113.10"


class DummyRequest:
    client = DummyClient()


class LocalIpv4MappedClient:
    host = "::ffff:127.0.0.1"


class LocalIpv4MappedRequest:
    client = LocalIpv4MappedClient()


def test_operator_guard_marks_remote_client_non_local() -> None:
    assert _is_local_client(DummyRequest()) is False


def test_operator_guard_allows_ipv4_mapped_localhost() -> None:
    assert _is_local_client(LocalIpv4MappedRequest()) is True


def test_operator_guard_uses_configurable_allowed_hosts(monkeypatch) -> None:
    monkeypatch.setattr(settings, "operator_allowed_client_hosts", "203.0.113.10")

    assert _is_local_client(DummyRequest()) is True


def test_operator_token_required_for_mutating_requests(monkeypatch) -> None:
    monkeypatch.setattr(settings, "operator_api_token", "secret-token")
    client = TestClient(app)

    response = client.patch("/api/auth/runtime-mode", json={"tdlib_use_test_dc": False})

    assert response.status_code == 401


def test_operator_token_allows_mutating_requests(monkeypatch) -> None:
    monkeypatch.setattr(settings, "operator_api_token", "secret-token")
    session_factory, _engine = make_session()

    with app_client(session_factory, role="admin") as client:
        response = client.patch(
            "/api/auth/runtime-mode",
            headers={"X-Operator-Token": "secret-token"},
            json={"tdlib_use_test_dc": False},
        )

    assert response.status_code == 200


def test_operator_guard_blocks_detailed_runtime_diagnostics(monkeypatch) -> None:
    monkeypatch.setattr(settings, "enforce_localhost_only", True)
    monkeypatch.setattr(settings, "operator_allowed_client_hosts", "127.0.0.1")
    monkeypatch.setattr(
        "app.api.diagnostics.build_runtime_diagnostics",
        lambda: {"database": "ok", "redis": "ok", "tdlib": "not_configured"},
    )
    client = TestClient(app)

    runtime = client.get("/diagnostics/runtime")
    frontend_summary = client.get("/diagnostics/frontend-summary")

    assert runtime.status_code == 403
    assert frontend_summary.status_code == 403


def test_worker_diagnostics_admin_response_is_safe_metadata(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    _, workspace = _seed_supabase_member(session_factory, role="admin")
    override_app_session(session_factory)
    monkeypatch.setattr(settings, "auth_mode", "supabase_jwt")
    monkeypatch.setattr(settings, "tdlib_database_root", "C:/real/session/db")
    monkeypatch.setattr(settings, "tdlib_files_root", "C:/real/session/files")
    monkeypatch.setattr("app.services.auth_context.SupabaseJwtVerifier.from_settings", lambda settings: _FakeVerifier())
    client = TestClient(app)

    try:
        response = client.get(
            "/api/workers/diagnostics",
            headers={"Authorization": "Bearer admin-token", "X-Workspace-Id": workspace.id},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "redis_rq"
    assert payload["redis"]["status"] in {"ok", "down"}
    assert "worker_count" in payload["redis"]
    assert {"auth_jobs", "profile_jobs", "warmup_jobs"}.issubset(
        {queue["name"] for queue in payload["queues"]}
    )
    serialized = str(payload)
    assert "session/db" not in serialized
    assert "session/files" not in serialized
    assert "C:/real" not in serialized
    assert "C:\\real" not in serialized
    assert "rediss://" not in serialized


def test_admin_diagnostics_endpoints_enforce_supabase_roles(monkeypatch) -> None:
    endpoints = ("/diagnostics/runtime", "/diagnostics/live-preflight", "/api/workers/diagnostics")
    for role in ("viewer", "operator", "admin"):
        session_factory, engine = create_sqlite_test_session_factory()
        Base.metadata.create_all(engine)
        _, workspace = _seed_supabase_member(session_factory, role=role)
        override_app_session(session_factory)
        monkeypatch.setattr(settings, "auth_mode", "supabase_jwt")
        monkeypatch.setattr("app.services.auth_context.SupabaseJwtVerifier.from_settings", lambda settings: _FakeVerifier())
        monkeypatch.setattr(
            "app.api.diagnostics.build_runtime_diagnostics",
            lambda: {"database": "ok", "redis": "ok", "tdlib": "not_configured"},
        )
        monkeypatch.setattr(
            "app.api.diagnostics.LivePreflightService.run",
            lambda self: {
                "tdjson_present": False,
                "tdlib_credentials_present": False,
                "postgres_reachable": True,
                "redis_reachable": True,
                "storage_writable": True,
                "rq_worker_expected": True,
                "rq_worker_status": "ready",
                "profile_worker_status": "ready",
                "auth_worker_status": "ready",
                "overall_status": "ready",
            },
        )
        client = TestClient(app)
        try:
            for endpoint in endpoints:
                response = client.get(endpoint)
                assert response.status_code == 401

                response = client.get(
                    endpoint,
                    headers={"Authorization": "Bearer role-token", "X-Workspace-Id": workspace.id},
                )
                assert response.status_code == (200 if role == "admin" else 403)
        finally:
            app.dependency_overrides.clear()


class _FakeVerifier:
    def verify(self, token: str) -> dict:
        assert token == "role-token" or token == "admin-token"
        return {"sub": "supabase-role-user", "email": "role@example.test"}


def _seed_supabase_member(session_factory, *, role: str) -> tuple[User, Workspace]:
    with session_factory() as session:
        user = User(
            email="role@example.test",
            external_auth_provider="supabase",
            external_auth_user_id="supabase-role-user",
            status="active",
        )
        session.add(user)
        session.flush()
        workspace = Workspace(name=f"{role} workspace", slug=f"{role}-workspace", owner_user_id=user.id, status="active")
        session.add(workspace)
        session.flush()
        session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role))
        session.add(WorkspacePlan(workspace_id=workspace.id))
        session.commit()
        return user, workspace


def test_cors_origin_parser_trims_configured_pages_origins(monkeypatch) -> None:
    monkeypatch.setattr(
        settings,
        "cors_origins",
        "https://stylisttg-dashboard.pages.dev, https://0df59c45.stylisttg-dashboard.pages.dev",
    )

    assert _configured_cors_origins() == [
        "https://stylisttg-dashboard.pages.dev",
        "https://0df59c45.stylisttg-dashboard.pages.dev",
    ]
