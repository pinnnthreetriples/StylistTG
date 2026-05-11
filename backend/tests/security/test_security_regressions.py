from __future__ import annotations

import json
import logging
from io import BytesIO

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from PIL import Image

from app.api.account_imports import _decode_optional_base64
from app.errors import AppError
from app.logging_utils import _JsonFormatter
from app.main import app
from app.models import Account, AccountStoryDraft, Asset, AssetKind, AssetStatus, User, Workspace, WorkspaceMember, WorkspacePlan
from app.services.account_update_jobs import build_account_update_preview
from app.services.dashboard import build_dashboard_profile
from app.services.assets import _open_verified_image
from app.services.jobs import build_profile_job_preview
from app.services.story_drafts import create_story_draft, delete_story_draft
from app.services.workspaces import ensure_default_workspace


def test_all_non_health_routes_require_auth_dependency() -> None:
    public_allowed = {"/health", "/ready"}
    missing: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.path in public_allowed:
            continue
        dependency_names: list[str] = []
        dependency_stack = list(route.dependant.dependencies)
        while dependency_stack:
            dependency = dependency_stack.pop()
            call = getattr(dependency, "call", None)
            dependency_names.append(getattr(call, "__name__", repr(call)))
            dependency_stack.extend(dependency.dependencies)
        if not any(name in {"require_authenticated", "require_mutation_permission", "dependency"} for name in dependency_names):
            methods = ",".join(sorted(route.methods or []))
            missing.append(f"{methods} {route.path}")

    assert missing == []


def test_story_post_delete_requires_authentication(db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.auth_context.settings.auth_mode", "supabase_jwt")
    response = TestClient(app).delete("/api/story-posts/story-id", headers={"X-Account-Id": "account-id"})

    # contract: unauthenticated DELETE returns 401 (no token) or 403 (token missing role).
    assert response.status_code in {401, 403}


def test_dashboard_profile_is_workspace_scoped(db_session) -> None:
    ensure_default_workspace(db_session)
    _, foreign_workspace = _seed_workspace(db_session, slug="foreign-dashboard")
    foreign_account = Account(workspace_id=foreign_workspace.id, external_ref="+15550000001")
    db_session.add(foreign_account)
    db_session.commit()

    with pytest.raises(ValueError, match="account not found"):
        build_dashboard_profile(db_session, foreign_account.id, workspace_id="00000000-0000-4000-8000-000000000002")


def test_story_draft_rejects_cross_workspace_asset(db_session) -> None:
    ensure_default_workspace(db_session)
    account = Account(workspace_id="00000000-0000-4000-8000-000000000002", external_ref="+15550000002")
    _, foreign_workspace = _seed_workspace(db_session, slug="foreign-story-asset")
    asset = _seed_asset(db_session, workspace_id=foreign_workspace.id, asset_id="foreign-story-asset")
    db_session.add(account)
    db_session.commit()

    with pytest.raises(ValueError, match="story asset not found"):
        create_story_draft(
            db_session,
            {
                "account_id": account.id,
                "asset_id": asset.id,
                "media_kind": "image",
                "privacy_preset": "contacts",
                "active_period_seconds": 86400,
            },
            workspace_id=account.workspace_id,
        )


def test_profile_job_preview_rejects_cross_workspace_asset(db_session) -> None:
    ensure_default_workspace(db_session)
    account = Account(workspace_id="00000000-0000-4000-8000-000000000002", external_ref="+15550000003")
    _, foreign_workspace = _seed_workspace(db_session, slug="foreign-profile-asset")
    asset = _seed_asset(db_session, workspace_id=foreign_workspace.id, asset_id="foreign-profile-asset")
    db_session.add(account)
    db_session.commit()

    with pytest.raises(ValueError, match="asset not found"):
        build_profile_job_preview(
            db_session,
            account_id=account.id,
            payload={"photo_asset_id": asset.id},
            workspace_id=account.workspace_id,
        )


def test_account_update_preview_rejects_cross_workspace_story_asset(db_session) -> None:
    ensure_default_workspace(db_session)
    account = Account(workspace_id="00000000-0000-4000-8000-000000000002", external_ref="+15550000004")
    _, foreign_workspace = _seed_workspace(db_session, slug="foreign-update-asset")
    asset = _seed_asset(db_session, workspace_id=foreign_workspace.id, asset_id="foreign-update-asset")
    db_session.add(account)
    db_session.commit()

    with pytest.raises(ValueError, match="story asset not found"):
        build_account_update_preview(
            db_session,
            account_id=account.id,
            desired_state={
                "stories": [
                    {
                        "action": "post_image",
                        "asset_id": asset.id,
                        "media_kind": "image",
                        "privacy_preset": "contacts",
                        "active_period_seconds": 86400,
                    }
                ]
            },
            workspace_id=account.workspace_id,
        )


def test_story_draft_orphaning_ignores_foreign_workspace_legacy_references(db_session) -> None:
    ensure_default_workspace(db_session)
    owner_account = Account(workspace_id="00000000-0000-4000-8000-000000000002", external_ref="+15550000005")
    _, foreign_workspace = _seed_workspace(db_session, slug="foreign-legacy-draft")
    foreign_account = Account(workspace_id=foreign_workspace.id, external_ref="+15550000006")
    db_session.add_all([owner_account, foreign_account])
    db_session.flush()
    asset = _seed_asset(db_session, workspace_id=owner_account.workspace_id, asset_id="owned-story-asset")
    owner_draft = create_story_draft(
        db_session,
        {
            "account_id": owner_account.id,
            "asset_id": asset.id,
            "media_kind": "image",
            "privacy_preset": "contacts",
            "active_period_seconds": 86400,
        },
        workspace_id=owner_account.workspace_id,
    )
    db_session.add(
        AccountStoryDraft(
            account_id=foreign_account.id,
            asset_id=asset.id,
            media_kind="image",
            privacy_preset="contacts",
            active_period_seconds=86400,
        )
    )
    db_session.commit()

    delete_story_draft(db_session, owner_draft.id, workspace_id=owner_account.workspace_id)

    assert db_session.get(Asset, asset.id).status == AssetStatus.ORPHANED


def test_json_formatter_redacts_sensitive_fields_and_exception_text() -> None:
    formatter = _JsonFormatter()
    try:
        raise RuntimeError("token=secret-token password=secret-password")
    except RuntimeError:
        record = logging.getLogger("test").makeRecord(
            "test",
            logging.ERROR,
            __file__,
            1,
            "",
            args=(),
            exc_info=True,
            extra={
                "event": "auth_code=12345",
                "fields": {
                    "operator_api_token": "operator-secret",
                    "nested": {"password": "password-secret"},
                    "message": "token=message-token postgres://user:db-password@example.test/db",
                    "safe": "visible",
                },
            },
        )
    payload = json.loads(formatter.format(record))

    encoded = json.dumps(payload)
    assert "operator-secret" not in encoded
    assert "password-secret" not in encoded
    assert "secret-token" not in encoded
    assert "secret-password" not in encoded
    assert "message-token" not in encoded
    assert "db-password" not in encoded
    assert payload["safe"] == "visible"


def test_image_upload_rejects_explicit_pixel_limit(monkeypatch) -> None:
    image_bytes = BytesIO()
    Image.new("RGB", (2, 2)).save(image_bytes, format="PNG")
    monkeypatch.setattr("app.services.assets.MAX_IMAGE_PIXELS", 3)

    with pytest.raises(ValueError, match="unsupported image"):
        _open_verified_image(image_bytes.getvalue(), error_message="unsupported image")


def test_import_base64_rejects_encoded_payload_before_decode(monkeypatch) -> None:
    monkeypatch.setattr("app.api.account_imports.settings.account_import_max_upload_bytes", 3)

    with pytest.raises(AppError) as exc_info:
        _decode_optional_base64("QUFBQUE=")

    assert exc_info.value.status_code == 413
    assert exc_info.value.error_code == "IMPORT_CONTENT_TOO_LARGE"


def test_import_base64_rejects_decoded_payload_over_exact_limit(monkeypatch) -> None:
    monkeypatch.setattr("app.api.account_imports.settings.account_import_max_upload_bytes", 1)

    with pytest.raises(AppError) as exc_info:
        _decode_optional_base64("QUFB")

    assert exc_info.value.status_code == 413
    assert exc_info.value.error_code == "IMPORT_CONTENT_TOO_LARGE"


def _seed_workspace(session, *, slug: str) -> tuple[User, Workspace]:
    user = User(
        email=f"{slug}@example.test",
        external_auth_provider="test",
        external_auth_user_id=slug,
        status="active",
    )
    session.add(user)
    session.flush()
    workspace = Workspace(name=slug, slug=slug, owner_user_id=user.id, status="active")
    session.add(workspace)
    session.flush()
    session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    session.add(WorkspacePlan(workspace_id=workspace.id))
    session.flush()
    return user, workspace


def _seed_asset(session, *, workspace_id: str, asset_id: str) -> Asset:
    asset = Asset(
        id=asset_id,
        workspace_id=workspace_id,
        kind=AssetKind.STORY_IMAGE,
        source_path="assets/source/story.jpg",
        normalized_path="assets/normalized/story.jpg",
        content_hash=f"{asset_id}-hash",
        mime="image/jpeg",
        status=AssetStatus.NORMALIZED,
    )
    session.add(asset)
    session.flush()
    return asset
