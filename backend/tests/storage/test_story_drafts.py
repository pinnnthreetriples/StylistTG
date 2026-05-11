from app.models import AccountState
from app.services.assets import get_asset
from app.services.accounts import create_account
from conftest import seed_story_asset


def test_story_draft_crud_contract(app_client, db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    asset = seed_story_asset(db_session)
    db_session.commit()

    create_response = app_client.post(
        "/api/story-drafts",
        json={
            "account_id": account.id,
            "asset_id": asset.id,
            "media_kind": "image",
            "caption": "Draft",
            "privacy_preset": "contacts",
            "active_period_seconds": 86400,
        },
    )
    assert create_response.status_code == 201
    draft = create_response.json()
    assert draft["caption"] == "Draft"

    patch_response = app_client.patch(
        f"/api/story-drafts/{draft['id']}", json={"caption": "Updated"}
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["caption"] == "Updated"

    list_response = app_client.get(f"/api/story-drafts/{account.id}")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [draft["id"]]

    delete_response = app_client.delete(f"/api/story-drafts/{draft['id']}")
    assert delete_response.status_code == 204
    assert get_asset(db_session, asset.id).status == "orphaned"


def test_story_draft_rejects_unchecked_premium_active_period(app_client, db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    asset = seed_story_asset(db_session)
    db_session.commit()

    response = app_client.post(
        "/api/story-drafts",
        json={
            "account_id": account.id,
            "asset_id": asset.id,
            "media_kind": "image",
            "active_period_seconds": 21600,
        },
    )
    assert response.status_code == 400
    assert (
        response.json()["message"]
        == "only 24h story active period is supported before live capability check"
    )
