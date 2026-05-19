from __future__ import annotations

from app.models import DEFAULT_LOCAL_WORKSPACE_ID
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.limits_service import LimitsService
from tests.helpers.factories import seed_two_workspaces


def _campaign(app_client) -> str:
    response = app_client.post("/api/neuro-commenting/campaigns", json={"name": "Limits"})
    assert response.status_code == 201
    return response.json()["id"]


def test_create_list_update_delete_limit(app_client) -> None:
    campaign_id = _campaign(app_client)
    create = app_client.post(
        f"/api/neuro-commenting/campaigns/{campaign_id}/limits",
        json={
            "scope_type": "account",
            "scope_id": "account-1",
            "limit_type": "comments_per_hour",
            "max_value": 3,
            "window_seconds": 3600,
            "enabled": True,
        },
    )
    assert create.status_code == 201
    limit_id = create.json()["id"]

    listed = app_client.get(f"/api/neuro-commenting/campaigns/{campaign_id}/limits")
    patched = app_client.patch(
        f"/api/neuro-commenting/limits/{limit_id}",
        json={"max_value": 4, "enabled": False},
    )
    deleted = app_client.delete(f"/api/neuro-commenting/limits/{limit_id}")

    assert listed.status_code == 200
    assert listed.json()["items"][0]["max_value"] == 3
    assert patched.status_code == 200
    assert patched.json()["max_value"] == 4
    assert patched.json()["enabled"] is False
    assert deleted.status_code == 204


def test_limit_validation_and_unknown_query_params(app_client) -> None:
    campaign_id = _campaign(app_client)

    bool_response = app_client.post(
        f"/api/neuro-commenting/campaigns/{campaign_id}/limits",
        json={
            "scope_type": "account",
            "scope_id": "account-1",
            "limit_type": "comments_per_hour",
            "max_value": True,
            "window_seconds": 3600,
        },
    )
    query_response = app_client.get(
        f"/api/neuro-commenting/campaigns/{campaign_id}/limits",
        params={"unexpected": "1"},
    )

    assert bool_response.status_code == 422
    assert bool_response.json()["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert query_response.status_code == 422
    assert query_response.json()["message"] == "unknown query parameter: unexpected"


def test_effective_defaults_returned_when_no_db_limits(db_session) -> None:
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Defaults"},
    )

    limits = LimitsService().resolve_effective_limits(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert {limit.limit_type for limit in limits} >= {
        "comments_per_hour",
        "comments_per_day",
        "min_delay_between_comments",
    }


def test_foreign_campaign_not_accessible(app_client, db_session) -> None:
    _own, foreign_workspace = seed_two_workspaces(db_session)
    foreign = CampaignService().create_campaign(
        db_session,
        workspace_id=foreign_workspace,
        actor_user_id="foreign",
        payload={"name": "Foreign"},
    )
    db_session.commit()

    response = app_client.get(f"/api/neuro-commenting/campaigns/{foreign.id}/limits")

    assert response.status_code == 404
    assert response.json()["error_code"] == "CAMPAIGN_NOT_FOUND"
