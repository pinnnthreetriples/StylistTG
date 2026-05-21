from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    AccountState,
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
    NeuroGeneratedApprovalStatus,
    NeuroSafetyStatus,
    new_id,
)
from app.services.neuro_commenting.campaign_account_service import CampaignAccountService
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.live_readiness_service import LiveReadinessService
from app.services.neuro_commenting.target_service import TargetService
from tests.helpers.factories import seed_account, seed_two_workspaces


@pytest.fixture(autouse=True)
def _allow_account_safety_gate(monkeypatch):
    def ok_gate(session, *, workspace_id: str, account_id: str, intent: str):
        _ = (session, workspace_id, account_id, intent)
        return SimpleNamespace(severity="ok", reasons=[])

    monkeypatch.setattr(
        "app.services.neuro_commenting.live_readiness_service.evaluate_safety_gate",
        ok_gate,
    )


def _config(*, send_enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(neuro_comment_tdlib_send_enabled=send_enabled)


def _campaign(db_session, *, active_account: bool = True, active_target: bool = True):
    account = seed_account(
        db_session,
        external_ref="+15550107001",
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Readiness", "dry_run": False, "send_mode": "manual_approval"},
    )
    campaign.status = "running"
    if active_account:
        CampaignAccountService().add_account(
            db_session,
            campaign_id=campaign.id,
            account_id=account.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            actor_user_id="user-1",
        )
    target = None
    if active_target:
        target = TargetService().add_target(
            db_session,
            campaign_id=campaign.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            actor_user_id="user-1",
            payload={"channel_ref": "@example", "discussion_chat_id": "discussion-1"},
        )
    db_session.commit()
    return account, campaign, target


def test_ready_false_when_no_active_account(db_session) -> None:
    _account, campaign, _target = _campaign(db_session, active_account=False)

    readiness = LiveReadinessService(config=_config(), limiter_ready=True).check(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert readiness.ready is False
    assert _has_blocker(readiness.checks, "NO_ACTIVE_ACCOUNT")


def test_ready_false_when_account_runtime_not_ready(db_session) -> None:
    account, campaign, _target = _campaign(db_session)
    account.runtime_state.runtime_health = "broken"
    db_session.commit()

    readiness = LiveReadinessService(config=_config(), limiter_ready=True).check(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert readiness.ready is False
    assert _has_blocker(readiness.checks, "ACCOUNT_RUNTIME_NOT_READY")


def test_ready_false_when_no_active_target(db_session) -> None:
    _account, campaign, _target = _campaign(db_session, active_target=False)

    readiness = LiveReadinessService(config=_config(), limiter_ready=True).check(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert readiness.ready is False
    assert _has_blocker(readiness.checks, "NO_ACTIVE_TARGET")


def test_ready_false_when_target_has_no_discussion_chat(db_session) -> None:
    _account, campaign, target = _campaign(db_session)
    assert target is not None
    target.discussion_chat_id = None
    db_session.commit()

    readiness = LiveReadinessService(config=_config(), limiter_ready=True).check(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert readiness.ready is False
    assert _has_blocker(readiness.checks, "TARGET_NO_DISCUSSION")


def test_ready_false_when_redis_limiter_is_denied(db_session) -> None:
    _account, campaign, _target = _campaign(db_session)

    readiness = LiveReadinessService(config=_config(), limiter_ready=False).check(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert readiness.ready is False
    assert _has_blocker(readiness.checks, "NEURO_COMMENT_RATE_LIMITER_NOT_READY")


def test_ready_false_when_approved_comment_mapping_is_missing(db_session) -> None:
    account, campaign, target = _campaign(db_session)
    assert target is not None
    observed = NeuroCommentObservedPost(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        source_chat_id="chat-1",
        source_message_id="msg-1",
        discussion_chat_id="discussion-1",
        discussion_message_id=None,
    )
    comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        account_id=account.id,
        observed_post_id=observed.id,
        generated_text="Интересно.",
        final_text="Интересно.",
        safety_status=NeuroSafetyStatus.PASSED.value,
        approval_status=NeuroGeneratedApprovalStatus.APPROVED.value,
    )
    db_session.add_all([observed, comment])
    db_session.commit()

    readiness = LiveReadinessService(config=_config(), limiter_ready=True).check(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert readiness.ready is False
    assert _has_blocker(readiness.checks, "DISCUSSION_MESSAGE_NOT_RESOLVED")


def test_ready_true_for_valid_manual_send_setup(db_session) -> None:
    _account, campaign, _target = _campaign(db_session)

    readiness = LiveReadinessService(config=_config(), limiter_ready=True).check(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert readiness.ready is True
    assert not [check for check in readiness.checks if check.severity == "blocker"]


def test_viewer_can_read_readiness(app_client, db_session) -> None:
    _account, campaign, _target = _campaign(db_session)

    response = app_client.get(f"/api/neuro-commenting/campaigns/{campaign.id}/live-readiness")

    assert response.status_code == 200
    assert response.json()["campaign_id"] == campaign.id


def test_foreign_workspace_readiness_returns_404(app_client, db_session) -> None:
    _own, foreign = seed_two_workspaces(db_session)
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=foreign,
        actor_user_id="foreign-user",
        payload={"name": "Foreign"},
    )
    db_session.commit()

    response = app_client.get(f"/api/neuro-commenting/campaigns/{campaign.id}/live-readiness")

    assert response.status_code == 404
    assert response.json()["error_code"] == "CAMPAIGN_NOT_FOUND"


def _has_blocker(checks, code: str) -> bool:
    return any(check.code == code and check.severity == "blocker" for check in checks)
