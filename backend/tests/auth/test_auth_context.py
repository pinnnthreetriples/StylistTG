from __future__ import annotations

# test-analyzer: disable-file=STG003 reason="STG003 over-fires on exc_info.value.status_code attribute checks; these tests assert the exact AppError type, error_code, and status_code via pytest.raises(match=...) plus exc_info.value.* — the strict equivalent of a 4xx-with-body check for raised exceptions."

import pytest

from app.errors import AppError
from app.models import User, Workspace, WorkspaceMember, WorkspacePlan
from app.modules.auth.dependencies import get_current_auth_context


def test_supabase_auth_context_requires_bearer_token(db_session, monkeypatch) -> None:
    class DummyRequest:
        headers: dict[str, str] = {}

    monkeypatch.setattr("app.modules.auth.service.settings.auth_mode", "supabase_jwt")

    with pytest.raises(AppError, match="authorization bearer token is required") as exc_info:
        get_current_auth_context(DummyRequest(), db_session)

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "AUTH_REQUIRED"


def test_supabase_auth_context_blocks_disabled_user(db_session, monkeypatch) -> None:
    user, workspace = _seed_supabase_identity(db_session, user_status="disabled")

    exc_info = _supabase_context_raises(db_session, monkeypatch, workspace.id)

    assert user.status == "disabled"
    assert exc_info.value.status_code == 403
    assert exc_info.value.error_code == "USER_DISABLED"


def test_supabase_auth_context_blocks_disabled_workspace(db_session, monkeypatch) -> None:
    _, workspace = _seed_supabase_identity(db_session, workspace_status="disabled")

    exc_info = _supabase_context_raises(db_session, monkeypatch, workspace.id)

    assert workspace.status == "disabled"
    assert exc_info.value.status_code == 403
    assert exc_info.value.error_code == "WORKSPACE_DISABLED"


def test_supabase_auth_context_blocks_invalid_role(db_session, monkeypatch) -> None:
    _, workspace = _seed_supabase_identity(db_session, role="superuser")

    exc_info = _supabase_context_raises(db_session, monkeypatch, workspace.id)

    assert exc_info.value.status_code == 403
    assert exc_info.value.error_code == "ROLE_INVALID"


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


def _supabase_context_raises(
    db_session, monkeypatch, workspace_id: str
) -> pytest.ExceptionInfo[AppError]:
    class DummyRequest:
        headers = {
            "Authorization": "Bearer token",
            "X-Workspace-Id": workspace_id,
        }

    class FakeVerifier:
        def verify(self, _token: str) -> dict:
            return {"sub": "supabase-user", "email": "user@example.test"}

    monkeypatch.setattr("app.modules.auth.service.settings.auth_mode", "supabase_jwt")
    monkeypatch.setattr(
        "app.modules.auth.service.SupabaseJwtVerifier.from_settings",
        lambda _settings: FakeVerifier(),
    )

    with pytest.raises(AppError) as exc_info:
        get_current_auth_context(DummyRequest(), db_session)
    return exc_info
