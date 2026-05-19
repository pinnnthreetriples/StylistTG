from __future__ import annotations

from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    NeuroCommentChannelRule,
    NeuroCommentTarget,
    new_id,
)
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.target_service import TargetService


def _seed_campaign(db_session):
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Bulk import"},
    )
    db_session.commit()
    return campaign


def test_bulk_targets_creates_unique_items(db_session) -> None:
    campaign = _seed_campaign(db_session)
    result = TargetService().bulk_add_targets(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        items=[
            {"channel_ref": "@alpha"},
            {"channel_ref": "@beta", "keywords": ["ai"]},
        ],
    )

    assert result.requested == 2
    assert len(result.created) == 2
    assert {target.channel_ref for target in result.created} == {"@alpha", "@beta"}
    assert result.skipped == []


def test_bulk_targets_skips_duplicates_inside_batch_and_db(db_session) -> None:
    campaign = _seed_campaign(db_session)
    # seed an existing target the second batch must skip
    existing = NeuroCommentTarget(
        id=new_id(),
        campaign_id=campaign.id,
        channel_ref="@existing",
        status="active",
        source_type="channel",
        keywords=[],
        exclude_keywords=[],
    )
    db_session.add(existing)
    db_session.commit()

    result = TargetService().bulk_add_targets(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        items=[
            {"channel_ref": "@existing"},
            {"channel_ref": "@new"},
            {"channel_ref": "@new"},
        ],
    )

    assert len(result.created) == 1
    skipped_reasons = {(skip.channel_ref, skip.reason) for skip in result.skipped}
    assert skipped_reasons == {("@existing", "duplicate"), ("@new", "duplicate")}


def test_bulk_targets_skips_blacklisted_workspace_refs(db_session) -> None:
    campaign = _seed_campaign(db_session)
    rule = NeuroCommentChannelRule(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        target_ref="@blocked",
        rule_type="blacklist",
        reason="test",
        created_by=None,
    )
    db_session.add(rule)
    db_session.commit()

    result = TargetService().bulk_add_targets(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        items=[{"channel_ref": "@blocked"}, {"channel_ref": "@ok"}],
    )

    assert {target.channel_ref for target in result.created} == {"@ok"}
    assert any(
        skip.channel_ref == "@blocked" and skip.reason == "blacklisted_workspace"
        for skip in result.skipped
    )


def test_bulk_targets_skips_invalid_refs(db_session) -> None:
    campaign = _seed_campaign(db_session)
    result = TargetService().bulk_add_targets(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        items=[{"channel_ref": "   "}, {"channel_ref": "@good"}],
    )

    assert {target.channel_ref for target in result.created} == {"@good"}
    assert any(skip.reason == "invalid_ref" for skip in result.skipped)


def test_bulk_targets_endpoint_returns_summary(app_client, db_session) -> None:
    campaign = _seed_campaign(db_session)

    response = app_client.post(
        f"/api/neuro-commenting/campaigns/{campaign.id}/targets/bulk",
        json={
            "items": [
                {"channel_ref": "@one"},
                {"channel_ref": "@one"},
                {"channel_ref": "@two", "keywords": ["ai"], "exclude_keywords": ["spam"]},
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["requested"] == 3
    assert {item["channel_ref"] for item in payload["created"]} == {"@one", "@two"}
    assert any(skip["reason"] == "duplicate" for skip in payload["skipped"])
