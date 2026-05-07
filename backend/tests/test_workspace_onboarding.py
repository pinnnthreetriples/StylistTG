from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings
from app.db import Base
from app.main import app
from app.models import User, Workspace, WorkspaceMember, WorkspacePlan
from app.services.auth_context import get_current_auth_context
from app.services.database import create_sqlite_test_session_factory
from app.services.workspaces import ensure_default_workspace

from conftest import override_app_session


def test_supabase_auth_context_onboards_personal_workspace_once(db_session, monkeypatch) -> None:
    class DummyRequest:
        headers = {"Authorization": "Bearer token-1"}

    class FakeVerifier:
        def verify(self, token: str) -> dict:
            assert token == "token-1"
            return {"sub": "supabase-user-1", "email": "new@example.test", "name": "New User"}

    monkeypatch.setattr("app.services.auth_context.settings.auth_mode", "supabase_jwt")
    monkeypatch.setattr("app.services.auth_context.SupabaseJwtVerifier.from_settings", lambda settings: FakeVerifier())

    first = get_current_auth_context(DummyRequest(), db_session)
    second = get_current_auth_context(DummyRequest(), db_session)

    assert first.auth_source == "supabase_jwt"
    assert first.workspace_id == second.workspace_id
    assert first.role == "owner"
    assert db_session.query(User).filter_by(external_auth_provider="supabase").count() == 1
    assert db_session.query(Workspace).count() == 1
    assert db_session.query(WorkspaceMember).count() == 1
    workspace = db_session.get(Workspace, first.workspace_id)
    plan = db_session.get(WorkspacePlan, first.workspace_id)
    assert workspace is not None
    assert workspace.name == "new@example.test workspace"
    assert plan is not None
    assert plan.plan_code == "starter"


def test_supabase_auth_context_rejects_foreign_workspace_header(db_session, monkeypatch) -> None:
    _, foreign_workspace = _seed_second_workspace(db_session)

    class DummyRequest:
        headers = {"Authorization": "Bearer token-1", "X-Workspace-Id": foreign_workspace.id}

    class FakeVerifier:
        def verify(self, token: str) -> dict:
            return {"sub": "supabase-user-1", "email": "new@example.test"}

    monkeypatch.setattr("app.services.auth_context.settings.auth_mode", "supabase_jwt")
    monkeypatch.setattr("app.services.auth_context.SupabaseJwtVerifier.from_settings", lambda settings: FakeVerifier())

    try:
        get_current_auth_context(DummyRequest(), db_session)
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        code = getattr(exc, "error_code", "")
    else:
        status_code = None
        code = ""

    assert status_code == 403
    assert code == "WORKSPACE_ACCESS_DENIED"


def test_get_me_returns_supabase_user_and_workspace(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    class FakeVerifier:
        def verify(self, token: str) -> dict:
            assert token == "token-1"
            return {"sub": "supabase-user-1", "email": "new@example.test", "name": "New User"}

    override_app_session(session_factory)
    monkeypatch.setattr(settings, "auth_mode", "supabase_jwt")
    monkeypatch.setattr("app.services.auth_context.SupabaseJwtVerifier.from_settings", lambda settings: FakeVerifier())
    try:
        response = TestClient(app).get("/api/me", headers={"Authorization": "Bearer token-1"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "user_id": response.json()["user_id"],
        "email": "new@example.test",
        "display_name": "New User",
        "workspace_id": response.json()["workspace_id"],
        "workspace_name": "new@example.test workspace",
        "role": "owner",
        "auth_source": "supabase_jwt",
    }
    assert "token-1" not in response.text


def _seed_second_workspace(session):
    from app.models import WorkspaceStatus

    ensure_default_workspace(session)
    user = User(
        email="second@example.test",
        external_auth_provider="test",
        external_auth_user_id="second-user",
        status="active",
    )
    session.add(user)
    session.flush()
    workspace = Workspace(
        name="Second",
        slug="second",
        owner_user_id=user.id,
        status=WorkspaceStatus.ACTIVE,
    )
    session.add(workspace)
    session.flush()
    session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    session.add(
        WorkspacePlan(
            workspace_id=workspace.id,
            plan_code="test",
            billing_status="active",
            max_accounts=1000,
            max_jobs_per_day=1000,
            max_batch_size=1000,
            max_storage_mb=1000,
            max_team_members=10,
        )
    )
    session.flush()
    return user, workspace
