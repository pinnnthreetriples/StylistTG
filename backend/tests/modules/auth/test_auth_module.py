from __future__ import annotations

from app.errors import AppError
from app.models import User, Workspace, WorkspaceMember, WorkspacePlan
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_mutation_permission, require_role
from app.modules.auth.service import resolve_auth_context


class DummyRequest:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = headers or {}


def test_local_mode_returns_default_workspace_auth_context(db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.modules.auth.service.settings.auth_mode", "local")

    context = resolve_auth_context(DummyRequest(), db_session)

    assert context.auth_source == "local"
    assert context.role == "owner"
    assert context.workspace_id
    assert context.user_id


def test_supabase_jwt_mode_resolves_user_workspace(db_session, monkeypatch) -> None:
    _, workspace = _seed_supabase_identity(db_session)
    monkeypatch.setattr("app.modules.auth.service.settings.auth_mode", "supabase_jwt")
    monkeypatch.setattr(
        "app.modules.auth.service.SupabaseJwtVerifier.from_settings",
        lambda _settings: _FakeVerifier(),
    )

    context = resolve_auth_context(
        DummyRequest({"Authorization": "Bearer token", "X-Workspace-Id": workspace.id}),
        db_session,
    )

    assert context == AuthContext(
        user_id=context.user_id,
        workspace_id=workspace.id,
        role="owner",
        auth_source="supabase_jwt",
    )


def test_workspace_access_denied_for_foreign_workspace(db_session, monkeypatch) -> None:
    _seed_supabase_identity(db_session)
    foreign = Workspace(name="Foreign", slug="foreign", owner_user_id="missing")
    db_session.add(foreign)
    db_session.commit()
    monkeypatch.setattr("app.modules.auth.service.settings.auth_mode", "supabase_jwt")
    monkeypatch.setattr(
        "app.modules.auth.service.SupabaseJwtVerifier.from_settings",
        lambda _settings: _FakeVerifier(),
    )

    error = _auth_error(
        lambda: resolve_auth_context(
            DummyRequest({"Authorization": "Bearer token", "X-Workspace-Id": foreign.id}),
            db_session,
        )
    )

    assert error == (403, "WORKSPACE_ACCESS_DENIED")


def test_require_mutation_permission_role_hierarchy() -> None:
    viewer = AuthContext("user", "workspace", "viewer", "test")
    operator = AuthContext("user", "workspace", "operator", "test")
    admin = AuthContext("user", "workspace", "admin", "test")
    owner = AuthContext("user", "workspace", "owner", "test")
    operator_guard = require_role("operator")

    assert _auth_error(lambda: operator_guard(viewer)) == (403, "ROLE_FORBIDDEN")
    assert require_mutation_permission(operator) is operator
    assert require_mutation_permission(admin) is admin
    assert require_mutation_permission(owner) is owner


def test_require_role_rejects_unknown_required_role() -> None:
    assert _auth_error(lambda: require_role("superuser")) == (403, "ROLE_INVALID")


def _seed_supabase_identity(
    session,
    *,
    user_status: str = "active",
    workspace_status: str = "active",
    role: str = "owner",
) -> tuple[User, Workspace]:
    user = User(
        email="user@example.test",
        external_auth_provider="supabase",
        external_auth_user_id="supabase-user",
        status=user_status,
    )
    session.add(user)
    session.flush()
    workspace = Workspace(
        name="Workspace",
        slug="workspace",
        owner_user_id=user.id,
        status=workspace_status,
    )
    session.add(workspace)
    session.flush()
    session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role))
    session.add(WorkspacePlan(workspace_id=workspace.id))
    session.commit()
    return user, workspace


class _FakeVerifier:
    def verify(self, token: str) -> dict[str, str]:
        assert token == "token"
        return {"sub": "supabase-user", "email": "user@example.test", "name": "User"}


def _auth_error(fn) -> tuple[int | None, str]:
    try:
        fn()
    except AppError as exc:
        return exc.status_code, exc.error_code
    return None, ""
