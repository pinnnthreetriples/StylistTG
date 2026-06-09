from __future__ import annotations

from app.config import Settings
from app.models import Asset, AssetKind
from app.modules.account_editing import router as account_editing_router
from tests.helpers.factories import seed_account_with_profile


def test_generate_bio_endpoint_returns_preview_only(app_client, db_session) -> None:
    account = seed_account_with_profile(db_session, index=1)
    account.profile_state.bio = "Existing bio"
    db_session.commit()

    response = app_client.post(
        f"/api/accounts/{account.id}/generate-bio",
        json={"language": "en", "persona_hints": {"role": "marketing"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["bio"]
    assert payload["provider"] == "fake"
    db_session.refresh(account.profile_state)
    assert account.profile_state.bio == "Existing bio"


def test_generate_avatar_endpoint_saves_asset_not_profile(
    app_client,
    db_session,
    monkeypatch,
    storage_dir,
) -> None:
    account = seed_account_with_profile(db_session, index=1)
    monkeypatch.setattr(
        account_editing_router,
        "settings",
        Settings(storage_local_root=storage_dir),
    )

    response = app_client.post(
        f"/api/accounts/{account.id}/generate-avatar",
        json={"persona_hints": {"role": "marketing"}},
    )

    assert response.status_code == 200
    payload = response.json()
    asset = db_session.get(Asset, payload["asset_id"])
    assert asset is not None
    assert asset.kind == AssetKind.PROFILE_PHOTO
    db_session.refresh(account.profile_state)
    assert account.profile_state.profile_photo_asset_id is None
