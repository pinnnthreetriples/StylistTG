from __future__ import annotations

import pytest

from app.models import (
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    NeuroCommentAttempt,
    NeuroCommentChannelRule,
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
    NeuroSafetyStatus,
    new_id,
)
from app.services.neuro_commenting import jobs
from app.services.neuro_commenting.campaign_account_service import CampaignAccountService
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.channel_rules_service import ChannelRulesService
from app.services.neuro_commenting.limits_service import LimitsService
from app.services.neuro_commenting.jobs import generate_comment, observe_target
from app.services.neuro_commenting.sender_service import SenderService
from app.services.neuro_commenting.errors import NeuroConflictError
from app.services.neuro_commenting.target_service import TargetService
from tests.helpers.factories import seed_account
from tests.test_neuro_commenting_rate_limiter import FakeRedis


class DenyLimiter:
    called = False

    def reserve(self, scope):
        self.called = True
        return type(
            "Reservation",
            (),
            {
                "allowed": False,
                "reservation_id": None,
                "reason": "account comments_per_hour limit exceeded",
                "retry_after_seconds": 60,
            },
        )()

    def commit(self, reservation):  # pragma: no cover - should not be called
        raise AssertionError("commit should not be called")

    def rollback(self, reservation):  # pragma: no cover - should not be called
        raise AssertionError("rollback should not be called")


def _campaign_target_comment(db_session):
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Safety"},
    )
    target = TargetService().add_target(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"channel_ref": "@safety"},
    )
    comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        generated_text="ok",
        final_text="ok",
        safety_status=NeuroSafetyStatus.PASSED.value,
    )
    attempt = NeuroCommentAttempt(
        id=new_id(),
        campaign_id=campaign.id,
        generated_comment_id=comment.id,
        target_id=target.id,
        status="created",
    )
    db_session.add_all([comment, attempt])
    db_session.commit()
    return campaign, target, comment, attempt


def test_rate_denied_marks_attempt_and_does_not_send(db_session) -> None:
    campaign, _target, comment, attempt = _campaign_target_comment(db_session)
    limiter = DenyLimiter()

    result = SenderService(limiter=limiter).send_comment(
        campaign=campaign, comment=comment, attempt=attempt
    )

    assert limiter.called is True
    assert result.status == "skipped"
    assert result.error_code == "RATE_LIMIT_DENIED"
    assert result.error_message == "account comments_per_hour limit exceeded"


def test_blacklisted_target_blocks_generation(db_session, monkeypatch) -> None:
    campaign, target, _comment, _attempt = _campaign_target_comment(db_session)
    campaign.status = "running"
    observed = NeuroCommentObservedPost(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        source_chat_id="chat",
        source_message_id="msg",
        post_text="hello",
    )
    db_session.add(observed)
    ChannelRulesService().create_rule(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"target_ref": target.channel_ref, "rule_type": "blacklist"},
    )
    db_session.commit()

    class FailingGenerator:
        def generate(self, prompt):  # pragma: no cover - must not be called
            _ = prompt
            raise AssertionError("AI provider was called for blacklisted target")

    monkeypatch.setattr(jobs, "build_ai_comment_generator", lambda: FailingGenerator())
    with pytest.raises(NeuroConflictError) as exc_info:
        generate_comment(
            db_session,
            campaign_id=campaign.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            observed_post_id=observed.id,
        )

    assert exc_info.value.error_code == "CHANNEL_RULE_BLOCKED"
    assert (
        db_session.query(NeuroCommentGeneratedComment)
        .filter_by(observed_post_id=observed.id)
        .count()
        == 0
    )


def test_blacklisted_target_blocks_observe_before_fetch(db_session) -> None:
    campaign, target, _comment, _attempt = _campaign_target_comment(db_session)
    campaign.status = "running"
    ChannelRulesService().create_rule(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"target_ref": target.channel_ref, "rule_type": "blacklist"},
    )
    db_session.commit()

    class FailingObserver:
        def refresh_target_metadata(self, account_id, target):  # pragma: no cover
            _ = (account_id, target)
            raise AssertionError("metadata fetch was called for blacklisted target")

        def fetch_recent_posts(self, account_id, target, limit):  # pragma: no cover
            _ = (account_id, target, limit)
            raise AssertionError("post fetch was called for blacklisted target")

    created = observe_target(
        db_session,
        campaign_id=campaign.id,
        target_id=target.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        observer=FailingObserver(),
    )

    assert created == []


def test_manual_send_uses_db_limits_before_send(db_session) -> None:
    campaign, target, comment, attempt = _campaign_target_comment(db_session)
    LimitsService().create_limit(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        payload={
            "scope_type": "target",
            "scope_id": target.id,
            "limit_type": "comments_per_hour",
            "max_value": 1,
            "window_seconds": 3600,
            "enabled": True,
        },
    )
    db_session.commit()
    redis = FakeRedis()
    limiter = SenderService(redis_client=redis)._limiter_for_send(db_session, campaign)
    first = limiter.reserve(
        type(
            "Scope",
            (),
            {
                "workspace_id": campaign.workspace_id,
                "campaign_id": campaign.id,
                "account_id": None,
                "target_id": target.id,
                "campaign_account_id": None,
                "campaign_target_id": None,
            },
        )()
    )
    limiter.commit(first)

    result = SenderService(redis_client=redis).send_comment(
        campaign=campaign, comment=comment, attempt=attempt
    )

    assert result.status == "skipped"
    assert result.error_code == "RATE_LIMIT_DENIED"


def test_blacklisted_target_blocks_send_before_limiter(db_session) -> None:
    campaign, target, comment, attempt = _campaign_target_comment(db_session)
    limiter = DenyLimiter()
    ChannelRulesService().create_rule(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"target_ref": target.channel_ref, "rule_type": "blacklist"},
    )
    db_session.commit()

    result = SenderService(limiter=limiter).send_comment(
        campaign=campaign, comment=comment, attempt=attempt
    )

    assert limiter.called is False
    assert result.status == "skipped"
    assert result.error_code == "CHANNEL_RULE_BLOCKED"


def test_sender_outcome_updates_account_and_target_health(db_session) -> None:
    campaign, target, comment, attempt = _campaign_target_comment(db_session)
    account = seed_account(
        db_session,
        external_ref="+15550106001",
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    CampaignAccountService().add_account(
        db_session,
        campaign_id=campaign.id,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
    )
    comment.account_id = account.id
    attempt.account_id = account.id
    db_session.commit()

    SenderService().record_attempt_success(
        db_session, campaign=campaign, comment=comment, attempt=attempt, telegram_message_id="tg-1"
    )

    assert attempt.status == "sent"
    assert target.success_count == 1
    assert target.health_score == 1.0

    SenderService().record_attempt_failure(
        db_session, campaign=campaign, comment=comment, attempt=attempt, error_code="FLOOD_WAIT"
    )

    assert attempt.status == "failed"
    assert target.flood_wait_count == 1
    assert target.health_score == 0.75


def test_sender_health_update_creates_auto_rule_suggestion(db_session) -> None:
    campaign, target, comment, attempt = _campaign_target_comment(db_session)
    target.health_score = 0.30
    target.fail_count = 2
    db_session.commit()

    SenderService().record_attempt_failure(
        db_session, campaign=campaign, comment=comment, attempt=attempt, error_code="FLOOD_WAIT"
    )

    assert (
        db_session.query(NeuroCommentChannelRule)
        .filter_by(target_ref=target.channel_ref, rule_type="auto_blacklist_suggested")
        .count()
        == 1
    )
