from __future__ import annotations

from datetime import UTC, datetime

from app.models import (
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    NeuroCommentAccountStats,
    NeuroCommentAttempt,
    NeuroCommentCampaignAccount,
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
    NeuroGeneratedApprovalStatus,
    NeuroSafetyStatus,
    new_id,
)
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.target_service import TargetService
from tests.helpers.factories import seed_account
from tests.helpers.factories import seed_two_workspaces


def _seed_analytics(db_session):
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Analytics"},
    )
    target = TargetService().add_target(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"channel_ref": "@analytics", "title": "Analytics"},
    )
    observed = NeuroCommentObservedPost(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        source_chat_id="chat",
        source_message_id="msg",
    )
    approved = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        observed_post_id=observed.id,
        generated_text="ok",
        final_text="ok",
        safety_status=NeuroSafetyStatus.PASSED.value,
        approval_status=NeuroGeneratedApprovalStatus.APPROVED.value,
    )
    rejected = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        generated_text="bad",
        final_text="bad",
        safety_status=NeuroSafetyStatus.PASSED.value,
        approval_status=NeuroGeneratedApprovalStatus.REJECTED.value,
    )
    sent_at = datetime(2026, 5, 19, 10, 0, tzinfo=UTC)
    failed_at = datetime(2026, 5, 19, 10, 1, tzinfo=UTC)
    sent = NeuroCommentAttempt(
        id=new_id(),
        campaign_id=campaign.id,
        generated_comment_id=approved.id,
        target_id=target.id,
        status="sent",
        telegram_message_id="tg-1",
        sent_at=sent_at,
    )
    failed = NeuroCommentAttempt(
        id=new_id(),
        campaign_id=campaign.id,
        generated_comment_id=rejected.id,
        target_id=target.id,
        status="failed",
        error_code="SEND_FAILED",
        failed_at=failed_at,
    )
    db_session.add_all([observed, approved, rejected, sent, failed])
    db_session.commit()
    return campaign, target


def test_analytics_endpoints_return_counts_rates_and_pages(app_client, db_session) -> None:
    campaign, target = _seed_analytics(db_session)

    stats = app_client.get(f"/api/neuro-commenting/campaigns/{campaign.id}/stats")
    channels = app_client.get(f"/api/neuro-commenting/campaigns/{campaign.id}/channel-stats")
    attempts = app_client.get(f"/api/neuro-commenting/campaigns/{campaign.id}/attempts")
    failures = app_client.get(f"/api/neuro-commenting/campaigns/{campaign.id}/failure-reasons")

    assert (
        stats.status_code,
        channels.status_code,
        attempts.status_code,
        failures.status_code,
    ) == (200, 200, 200, 200)
    assert stats.json()["posts_seen"] == 1
    assert stats.json()["comments_generated"] == 2
    assert stats.json()["comments_approved"] == 1
    assert stats.json()["comments_rejected"] == 1
    assert stats.json()["comments_sent"] == 1
    assert channels.json()["items"][0]["target_id"] == target.id
    assert channels.json()["items"][0]["rule_status"] == "none"
    assert channels.json()["items"][0]["last_success_at"] is not None
    assert channels.json()["items"][0]["last_failure_at"] is not None
    assert attempts.json()["total"] == 2
    assert failures.json()["items"][0]["error_code"] == "SEND_FAILED"


def test_account_stats_include_campaign_account_status_and_cooldown(app_client, db_session) -> None:
    campaign, _target = _seed_analytics(db_session)
    account = seed_account(
        db_session,
        external_ref="+15550105001",
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    cooldown_until = datetime(2099, 1, 1, tzinfo=UTC)
    db_session.add_all(
        [
            NeuroCommentCampaignAccount(
                id=new_id(),
                campaign_id=campaign.id,
                account_id=account.id,
                status="cooldown",
                cooldown_until=cooldown_until,
            ),
            NeuroCommentAccountStats(
                id=new_id(),
                campaign_id=campaign.id,
                account_id=account.id,
                comments_sent=2,
                comments_failed=1,
                success_rate=2 / 3,
            ),
        ]
    )
    db_session.commit()

    response = app_client.get(f"/api/neuro-commenting/campaigns/{campaign.id}/account-stats")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["status"] == "cooldown"
    assert item["cooldown_until"] is not None


def test_account_stats_include_campaign_accounts_without_events(app_client, db_session) -> None:
    campaign, _target = _seed_analytics(db_session)
    account = seed_account(
        db_session,
        external_ref="+15550105002",
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    db_session.add(
        NeuroCommentCampaignAccount(
            id=new_id(),
            campaign_id=campaign.id,
            account_id=account.id,
            status="active",
        )
    )
    db_session.commit()

    response = app_client.get(f"/api/neuro-commenting/campaigns/{campaign.id}/account-stats")

    assert response.status_code == 200
    item = next(item for item in response.json()["items"] if item["account_id"] == account.id)
    assert item["comments_sent"] == 0
    assert item["comments_failed"] == 0
    assert item["flood_wait_count"] == 0
    assert item["status"] == "active"


def test_failure_reasons_total_counts_all_groups(app_client, db_session) -> None:
    campaign, target = _seed_analytics(db_session)
    comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        generated_text="bad2",
        final_text="bad2",
        safety_status=NeuroSafetyStatus.PASSED.value,
        approval_status=NeuroGeneratedApprovalStatus.REJECTED.value,
    )
    db_session.add(comment)
    db_session.flush()
    db_session.add(
        NeuroCommentAttempt(
            id=new_id(),
            campaign_id=campaign.id,
            generated_comment_id=comment.id,
            target_id=target.id,
            status="failed",
            error_code="PERMISSION_DENIED",
            failed_at=datetime(2026, 5, 19, 10, 2, tzinfo=UTC),
        )
    )
    db_session.commit()

    response = app_client.get(
        f"/api/neuro-commenting/campaigns/{campaign.id}/failure-reasons?limit=1"
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_campaign_stats_count_flood_wait_error_code(app_client, db_session) -> None:
    campaign, target = _seed_analytics(db_session)
    comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        generated_text="flood",
        final_text="flood",
        safety_status=NeuroSafetyStatus.PASSED.value,
        approval_status=NeuroGeneratedApprovalStatus.APPROVED.value,
    )
    db_session.add(comment)
    db_session.flush()
    db_session.add(
        NeuroCommentAttempt(
            id=new_id(),
            campaign_id=campaign.id,
            generated_comment_id=comment.id,
            target_id=target.id,
            status="failed",
            error_code="FLOOD_WAIT",
            failed_at=datetime(2026, 5, 19, 10, 3, tzinfo=UTC),
        )
    )
    db_session.commit()

    response = app_client.get(f"/api/neuro-commenting/campaigns/{campaign.id}/stats")

    assert response.status_code == 200
    assert response.json()["flood_wait_count"] == 1


def test_analytics_foreign_campaign_returns_404(app_client, db_session) -> None:
    _own, foreign_workspace = seed_two_workspaces(db_session)
    foreign = CampaignService().create_campaign(
        db_session,
        workspace_id=foreign_workspace,
        actor_user_id="foreign",
        payload={"name": "Foreign"},
    )
    db_session.commit()

    response = app_client.get(f"/api/neuro-commenting/campaigns/{foreign.id}/stats")

    assert response.status_code == 404
    assert response.json()["error_code"] == "CAMPAIGN_NOT_FOUND"
