from __future__ import annotations

import pytest

from app.main import app
from app.models import (
    DEFAULT_LOCAL_USER_ID,
    DEFAULT_LOCAL_WORKSPACE_ID,
    SensitiveAuditEvent,
    Workspace,
)
from app.services.auth_context import AuthContext, get_current_auth_context
from app.services.feature_flags import is_safety_pipeline_v2_enabled
from app.services.workspaces import ensure_default_workspace
from tests.helpers.factories import seed_two_workspaces


def _auth(
    *,
    role: str = "admin",
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
) -> AuthContext:
    return AuthContext(
        user_id=DEFAULT_LOCAL_USER_ID,
        workspace_id=workspace_id,
        role=role,
        auth_source="test",
    )


@pytest.fixture()
def admin_client(app_client):
    app.dependency_overrides[get_current_auth_context] = lambda: _auth(role="admin")
    return app_client


def test_workspace_feature_flag_defaults_false(db_session) -> None:
    _user, workspace, _member = ensure_default_workspace(db_session)

    assert workspace.safety_pipeline_v2_enabled is False
    assert is_safety_pipeline_v2_enabled(db_session, workspace.id) is False


def test_feature_flag_service_returns_true_when_enabled(db_session) -> None:
    _user, workspace, _member = ensure_default_workspace(db_session)
    workspace.safety_pipeline_v2_enabled = True
    db_session.commit()

    assert is_safety_pipeline_v2_enabled(db_session, workspace.id) is True


def test_patch_feature_flags_admin_updates_workspace_and_audits(
    admin_client,
    db_session,
) -> None:
    ensure_default_workspace(db_session)

    response = admin_client.patch(
        f"/api/workspaces/{DEFAULT_LOCAL_WORKSPACE_ID}/feature-flags",
        json={"safety_pipeline_v2_enabled": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == DEFAULT_LOCAL_WORKSPACE_ID
    assert payload["safety_pipeline_v2_enabled"] is True
    workspace = db_session.get(Workspace, DEFAULT_LOCAL_WORKSPACE_ID)
    assert workspace.safety_pipeline_v2_enabled is True

    event = db_session.query(SensitiveAuditEvent).one()
    assert event.workspace_id == DEFAULT_LOCAL_WORKSPACE_ID
    assert event.actor_user_id == DEFAULT_LOCAL_USER_ID
    assert event.action == "workspace.feature_flag.updated"
    assert event.entity_type == "workspace"
    assert event.entity_id == DEFAULT_LOCAL_WORKSPACE_ID
    assert event.metadata_json == {
        "flag": "safety_pipeline_v2_enabled",
        "new_value": True,
    }


def test_patch_feature_flags_non_admin_returns_403(app_client, db_session) -> None:
    ensure_default_workspace(db_session)
    app.dependency_overrides[get_current_auth_context] = lambda: _auth(role="operator")

    response = app_client.patch(
        f"/api/workspaces/{DEFAULT_LOCAL_WORKSPACE_ID}/feature-flags",
        json={"safety_pipeline_v2_enabled": True},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error_code"] == "ROLE_FORBIDDEN"
    assert body["error_class"] == "forbidden"


def test_patch_feature_flags_cross_tenant_returns_404(app_client, db_session) -> None:
    _own_workspace, foreign_workspace = seed_two_workspaces(db_session)
    app.dependency_overrides[get_current_auth_context] = lambda: _auth(role="admin")

    response = app_client.patch(
        f"/api/workspaces/{foreign_workspace}/feature-flags",
        json={"safety_pipeline_v2_enabled": True},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "WORKSPACE_NOT_FOUND"
    assert body["error_class"] == "not_found"
