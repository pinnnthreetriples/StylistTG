from __future__ import annotations

# test-analyzer: disable-file=TQA008 reason="manual try/except pattern; replaced with pytest.raises(match=...) in #263"
# test-analyzer: disable-file=STG003 reason="4xx assertion without typed error body; tightened in #263"

from app.models import User, Workspace, WorkspaceMember, WorkspacePlan
from app.services.auth_context import get_current_auth_context


def test_supabase_auth_context_requires_bearer_token(db_session, monkeypatch) -> None:
    class DummyRequest:
        headers: dict[str, str] = {}

    monkeypatch.setattr("app.services.auth_context.settings.auth_mode", "supabase_jwt")

    try:
        get_current_auth_context(DummyRequest(), db_session)
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        code = getattr(exc, "error_code", "")
    else:
        status_code = None
        code = ""

    assert status_code == 401
    assert code == "AUTH_REQUIRED"


def test_supabase_auth_context_blocks_disabled_user(db_session, monkeypatch) -> None:
    user, workspace = _seed_supabase_identity(db_session, user_status="disabled")

    context_error = _supabase_context_error(db_session, monkeypatch, workspace.id)

    assert user.status == "disabled"
    assert context_error == (403, "USER_DISABLED")


def test_supabase_auth_context_blocks_disabled_workspace(db_session, monkeypatch) -> None:
    _, workspace = _seed_supabase_identity(db_session, workspace_status="disabled")

    context_error = _supabase_context_error(db_session, monkeypatch, workspace.id)

    assert workspace.status == "disabled"
    assert context_error == (403, "WORKSPACE_DISABLED")


def test_supabase_auth_context_blocks_invalid_role(db_session, monkeypatch) -> None:
    _, workspace = _seed_supabase_identity(db_session, role="superuser")

    context_error = _supabase_context_error(db_session, monkeypatch, workspace.id)

    assert context_error == (403, "ROLE_INVALID")


def _seed_supabase_identity(
    session,
    *,
    user_status: str = "active",
    workspace_status: str = "active",
    role: str = "owner",
):
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


def _supabase_context_error(db_session, monkeypatch, workspace_id: str) -> tuple[int | None, str]:
    class DummyRequest:
        headers = {
            "Authorization": "Bearer token",
            "X-Workspace-Id": workspace_id,
        }

    class FakeVerifier:
        def verify(self, _token: str) -> dict:
            return {"sub": "supabase-user", "email": "user@example.test"}

    monkeypatch.setattr("app.services.auth_context.settings.auth_mode", "supabase_jwt")
    monkeypatch.setattr(
        "app.services.auth_context.SupabaseJwtVerifier.from_settings",
        lambda _settings: FakeVerifier(),
    )

    try:
        get_current_auth_context(DummyRequest(), db_session)
    except Exception as exc:
        return getattr(exc, "status_code", None), getattr(exc, "error_code", "")
    return None, ""
