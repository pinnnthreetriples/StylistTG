from __future__ import annotations

from sqlalchemy import UniqueConstraint

from app.models import DEFAULT_LOCAL_WORKSPACE_ID, NeuroCommentChannelRule
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.channel_rules_service import ChannelRulesService
from app.services.neuro_commenting.target_service import TargetService


def _campaign_and_target(db_session):
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Rules"},
    )
    campaign.status = "running"
    target = TargetService().add_target(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"channel_ref": "@rules"},
    )
    db_session.commit()
    return campaign, target


def test_create_list_delete_rule_and_policy_blocks_blacklist(db_session) -> None:
    _campaign, target = _campaign_and_target(db_session)
    service = ChannelRulesService()

    rule = service.create_rule(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"target_ref": target.channel_ref, "rule_type": "blacklist", "reason": "bad"},
    )
    listed, total = service.list_rules(db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID)
    decision = service.evaluate_target_allowed(
        db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID, target=target
    )
    service.delete_rule(db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID, rule_id=rule.id)
    allowed = service.evaluate_target_allowed(
        db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID, target=target
    )

    assert total == 1
    assert listed[0].id == rule.id
    assert decision.allowed is False
    assert decision.reason == "blacklisted"
    assert allowed.allowed is True


def test_create_rule_deduplicates_same_workspace_target_and_type(db_session) -> None:
    _campaign, target = _campaign_and_target(db_session)
    service = ChannelRulesService()

    first = service.create_rule(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"target_ref": target.channel_ref, "rule_type": "blacklist", "reason": "bad"},
    )
    duplicate = service.create_rule(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-2",
        payload={
            "target_ref": f" {target.channel_ref} ",
            "rule_type": "blacklist",
            "reason": "still bad",
        },
    )
    listed, total = service.list_rules(db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID)

    assert duplicate.id == first.id
    assert total == 1
    assert [rule.id for rule in listed] == [first.id]


def test_channel_rule_model_has_database_deduplication_constraint() -> None:
    unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in NeuroCommentChannelRule.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("workspace_id", "target_ref", "rule_type") in unique_columns


def test_auto_suggestion_does_not_block_and_pause_resume_target(db_session) -> None:
    _campaign, target = _campaign_and_target(db_session)
    service = ChannelRulesService()
    service.create_rule(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={
            "target_ref": target.channel_ref,
            "rule_type": "auto_blacklist_suggested",
            "reason": "low health",
        },
    )
    suggested = service.evaluate_target_allowed(
        db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID, target=target
    )
    service.pause_target(
        db_session,
        target_id=target.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
    )
    paused = service.evaluate_target_allowed(
        db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID, target=target
    )
    service.resume_target(
        db_session,
        target_id=target.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
    )

    assert suggested.allowed is True
    assert paused.allowed is False
    assert paused.reason == "target_paused"
    assert target.status == "active"


def test_channel_rules_api_flow(app_client) -> None:
    campaign_id = app_client.post("/api/neuro-commenting/campaigns", json={"name": "Rules"}).json()[
        "id"
    ]
    target = app_client.post(
        f"/api/neuro-commenting/campaigns/{campaign_id}/targets",
        json={"channel_ref": "@rules-api"},
    ).json()

    created = app_client.post(
        "/api/neuro-commenting/channel-rules",
        json={"target_ref": "@rules-api", "rule_type": "whitelist", "reason": "trusted"},
    )
    listed = app_client.get("/api/neuro-commenting/channel-rules")
    pause = app_client.post(f"/api/neuro-commenting/targets/{target['id']}/pause")
    resume = app_client.post(f"/api/neuro-commenting/targets/{target['id']}/resume")
    deleted = app_client.delete(f"/api/neuro-commenting/channel-rules/{created.json()['id']}")

    assert created.status_code == 201
    assert listed.status_code == 200
    assert pause.status_code == 200
    assert resume.status_code == 200
    assert deleted.status_code == 204


def test_channel_rule_rejects_blank_target_ref(app_client) -> None:
    response = app_client.post(
        "/api/neuro-commenting/channel-rules",
        json={"target_ref": "   ", "rule_type": "blacklist"},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "REQUEST_VALIDATION_ERROR"
