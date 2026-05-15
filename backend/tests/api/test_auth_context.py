from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings
from app.db import Base
from app.main import app
from app.models import User, Workspace, WorkspaceMember, WorkspacePlan
from app.services.database import create_sqlite_test_session_factory

from conftest import override_app_session


def test_api_me_requires_bearer_token_in_supabase_mode(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    override_app_session(session_factory)
    monkeypatch.setattr(settings, "auth_mode", "supabase_jwt")
    try:
        response = TestClient(app).get("/api/me")
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH_REQUIRED"


def test_api_me_resolves_supabase_workspace(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        _, workspace = _seed_supabase_identity(session)
    override_app_session(session_factory)
    monkeypatch.setattr(settings, "auth_mode", "supabase_jwt")
    monkeypatch.setattr(
        "app.services.auth_context.SupabaseJwtVerifier.from_settings",
        lambda _settings: _FakeVerifier(),
    )
    try:
        response = TestClient(app).get(
            "/api/me",
            headers={"Authorization": "Bearer token", "X-Workspace-Id": workspace.id},
        )
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "user@example.test"
    assert payload["workspace_id"] == workspace.id
    assert payload["role"] == "owner"
    assert payload["auth_source"] == "supabase_jwt"


def _seed_supabase_identity(session) -> tuple[User, Workspace]:
    user = User(
        email="user@example.test",
        external_auth_provider="supabase",
        external_auth_user_id="supabase-user",
        status="active",
    )
    session.add(user)
    session.flush()
    workspace = Workspace(
        name="Workspace",
        slug="workspace",
        owner_user_id=user.id,
        status="active",
    )
    session.add(workspace)
    session.flush()
    session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    session.add(WorkspacePlan(workspace_id=workspace.id))
    session.commit()
    return user, workspace


class _FakeVerifier:
    def verify(self, token: str) -> dict[str, str]:
        assert token == "token"
        return {"sub": "supabase-user", "email": "user@example.test", "name": "User"}
