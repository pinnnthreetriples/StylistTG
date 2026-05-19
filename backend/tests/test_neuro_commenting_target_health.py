from __future__ import annotations

from app.models import DEFAULT_LOCAL_WORKSPACE_ID, NeuroCommentChannelRule
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.target_health_service import TargetHealthService
from app.services.neuro_commenting.target_service import TargetService


def _target(db_session):
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Health"},
    )
    target = TargetService().add_target(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"channel_ref": "@health"},
    )
    db_session.commit()
    return campaign, target


def test_health_score_deltas_clamp_and_suggest_blacklist(db_session) -> None:
    _campaign, target = _target(db_session)
    target.health_score = 0.30
    target.fail_count = 2
    service = TargetHealthService()

    service.record_target_failure(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        target_id=target.id,
        error_code="COMMENTS_DISABLED",
    )
    service.record_target_flood_wait(
        db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID, target_id=target.id
    )
    service.record_deleted_comment(
        db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID, target_id=target.id
    )
    service.suggest_rules_for_target(
        db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID, target_id=target.id
    )

    assert target.health_score == 0.0
    assert target.fail_count >= 3
    assert (
        db_session.query(NeuroCommentChannelRule)
        .filter_by(rule_type="auto_blacklist_suggested", target_ref=target.channel_ref)
        .count()
        == 1
    )


def test_success_suggests_whitelist_without_duplicates(db_session) -> None:
    _campaign, target = _target(db_session)
    target.health_score = 0.84
    target.success_count = 4
    service = TargetHealthService()

    service.record_target_success(
        db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID, target_id=target.id
    )
    service.suggest_rules_for_target(
        db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID, target_id=target.id
    )
    service.suggest_rules_for_target(
        db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID, target_id=target.id
    )

    assert target.health_score == 0.89
    assert (
        db_session.query(NeuroCommentChannelRule)
        .filter_by(rule_type="auto_whitelist_suggested", target_ref=target.channel_ref)
        .count()
        == 1
    )
