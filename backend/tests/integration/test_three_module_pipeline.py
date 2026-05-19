"""Phase 0 Task 5 end-to-end smoke for the neuro-commenting pipeline.

Drives the real ``observe_target`` job (which internally generates a comment
and ``ApprovalService`` (which prepares the send attempt) using the in-memory
fakes from ``tests._fakes.fake_tdlib_runtime``. The objective is to prove the
glue between observation, AI generation, safety, approval and attempt
creation works without involving TDLib.
"""

from __future__ import annotations

from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    AccountState,
    NeuroAttemptStatus,
    NeuroCommentAttempt,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
    NeuroGeneratedApprovalStatus,
    NeuroSafetyStatus,
)
from app.services.neuro_commenting.enums import NeuroObservedPostStatus
from app.services.neuro_commenting.approval_service import ApprovalService
from app.services.neuro_commenting.campaign_account_service import CampaignAccountService
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.jobs import observe_target
from app.services.neuro_commenting.target_service import TargetService
from tests._fakes.fake_tdlib_runtime import FakeTdlibRuntime
from tests.helpers.factories import seed_account


WORKSPACE = DEFAULT_LOCAL_WORKSPACE_ID


def _seed_pipeline(db_session, *, mode: str = "all_posts"):
    account = seed_account(
        db_session,
        external_ref="+15550107001",
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=WORKSPACE,
        actor_user_id="user-1",
        payload={"name": "Phase 0 E2E", "mode": mode, "send_mode": "manual_approval"},
    )
    campaign.status = "running"
    CampaignAccountService().add_account(
        db_session,
        campaign_id=campaign.id,
        account_id=account.id,
        workspace_id=WORKSPACE,
        actor_user_id="user-1",
    )
    target = TargetService().add_target(
        db_session,
        campaign_id=campaign.id,
        workspace_id=WORKSPACE,
        actor_user_id="user-1",
        payload={
            "channel_ref": "@phase0_e2e",
            "channel_id": "chan-1",
            "discussion_chat_id": "discussion-1",
            "title": "Phase 0 E2E channel",
            "username": "phase0_e2e",
        },
    )
    db_session.commit()
    return account, campaign, target


def test_full_observe_to_attempt_pipeline_with_fake_tdlib(db_session) -> None:
    _account, campaign, target = _seed_pipeline(db_session)
    runtime = FakeTdlibRuntime()
    runtime.seed_metadata_from_target(target)
    runtime.observer.add_post(
        source_chat_id="chan-1",
        source_message_id="msg-1",
        post_text="Сегодня поговорим о Telegram автоматизации",
        language="ru",
    )

    created = observe_target(
        db_session,
        campaign_id=campaign.id,
        target_id=target.id,
        workspace_id=WORKSPACE,
        observer=runtime.build_observer(),
    )

    assert len(created) == 1
    observed = created[0]
    db_session.refresh(observed)
    assert observed.status == NeuroObservedPostStatus.GENERATED.value
    assert observed.discussion_chat_id == "discussion-1"

    comment = (
        db_session.query(NeuroCommentGeneratedComment)
        .filter(NeuroCommentGeneratedComment.observed_post_id == observed.id)
        .one()
    )
    assert comment.approval_status == NeuroGeneratedApprovalStatus.PENDING.value
    assert comment.safety_status in {
        NeuroSafetyStatus.PASSED.value,
        NeuroSafetyStatus.NEEDS_REVIEW.value,
    }
    assert comment.provider == "fake"

    _approved, attempt = ApprovalService().approve_comment(
        db_session,
        comment_id=comment.id,
        workspace_id=WORKSPACE,
        actor_user_id="user-1",
    )
    db_session.commit()

    db_session.refresh(attempt)
    assert attempt.status == NeuroAttemptStatus.CREATED.value
    assert attempt.generated_comment_id == comment.id

    persisted = db_session.query(NeuroCommentAttempt).filter_by(id=attempt.id).one()
    assert persisted.account_id == comment.account_id
    assert persisted.target_id == target.id

    observed_events = {
        event.event_type
        for event in db_session.query(NeuroCommentEvent)
        .filter(NeuroCommentEvent.workspace_id == WORKSPACE)
        .all()
    }
    assert {"post_observed", "ai_generation_started", "comment_approved"} <= observed_events


def test_ai_failure_marks_observed_post_failed(db_session) -> None:
    _account, campaign, target = _seed_pipeline(db_session)
    runtime = FakeTdlibRuntime()
    runtime.seed_metadata_from_target(target)
    runtime.observer.add_post(
        source_chat_id="chan-1",
        source_message_id="msg-1",
        post_text="trigger ai failure",
        language="ru",
    )
    runtime.force_ai_failure(error_code="AI_TIMEOUT")

    # Patch the AI generator factory to inject the failing provider.
    from app.services.neuro_commenting import ai_comment_generator as ai_module
    from app.services.neuro_commenting import jobs as jobs_module

    original = ai_module.build_ai_comment_generator
    ai_module.build_ai_comment_generator = lambda *_a, **_k: ai_module.AICommentGenerator(
        runtime.ai_provider
    )
    jobs_module.build_ai_comment_generator = ai_module.build_ai_comment_generator
    try:
        observe_target(
            db_session,
            campaign_id=campaign.id,
            target_id=target.id,
            workspace_id=WORKSPACE,
            observer=runtime.build_observer(),
        )
    finally:
        ai_module.build_ai_comment_generator = original
        jobs_module.build_ai_comment_generator = original

    observed = (
        db_session.query(NeuroCommentObservedPost)
        .filter(NeuroCommentObservedPost.campaign_id == campaign.id)
        .one()
    )
    assert observed.status == NeuroObservedPostStatus.FAILED.value
    failure_events = (
        db_session.query(NeuroCommentEvent)
        .filter(NeuroCommentEvent.event_type == "ai_generation_failed")
        .all()
    )
    assert len(failure_events) == 1
    assert failure_events[0].data_json["error_code"] == "AI_TIMEOUT"
