from __future__ import annotations


from sqlalchemy.orm import Session

from app.models import (
    NeuroCommentGeneratedComment,
    new_id,
    utc_now,
)
from app.modules.neuro_commenting.account_selector import AccountSelector
from app.modules.neuro_commenting.ai_comment_generator import (
    AICommentGenerationError,
)
from app.modules.neuro_commenting.analytics_service import AnalyticsService
from app.modules.neuro_commenting.enums import (
    NeuroEventLevel,
    NeuroGeneratedApprovalStatus,
    NeuroObservedPostStatus,
)
from app.modules.neuro_commenting.errors import (
    NeuroConflictError,
)
from app.modules.neuro_commenting.prompt_builder import PromptBuilder
from app.modules.neuro_commenting.channel_rules_service import ChannelRulesService
from app.modules.neuro_commenting.safety_policy import (
    AccountSafetySnapshot,
    CampaignSafetySnapshot,
    SafetyPolicy,
    TargetSafetySnapshot,
)
from app.modules.neuro_commenting import repository


class NeuroCommentJobNotImplementedError(RuntimeError):
    pass


def generate_comment(
    session: Session,
    *,
    campaign_id: str,
    workspace_id: str,
    observed_post_id: str,
    force: bool = False,
) -> NeuroCommentGeneratedComment:
    campaign = repository.require_campaign(
        session, campaign_id=campaign_id, workspace_id=workspace_id
    )
    observed_post = repository.get_observed_post(
        session, observed_post_id=observed_post_id, campaign_id=campaign.id
    )
    if observed_post is None:
        raise ValueError("observed post not found")
    if not force:
        existing_comment = repository.get_generated_comment_for_observed_post(
            session, observed_post_id=observed_post.id
        )
        if existing_comment is not None:
            return existing_comment
    target = repository.require_target(
        session, target_id=observed_post.target_id, campaign_id=campaign.id
    )
    rule_decision = ChannelRulesService().evaluate_target_allowed(
        session, workspace_id=workspace_id, target=target
    )
    if not rule_decision.allowed:
        observed_post.status = NeuroObservedPostStatus.FAILED.value
        observed_post.processed_at = utc_now()
        AnalyticsService().write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            target_id=target.id,
            observed_post_id=observed_post.id,
            event_type="channel_rule_blocked",
            event_level=NeuroEventLevel.WARNING,
            message="channel rule blocked neuro-comment generation",
            data={
                "error_code": "CHANNEL_RULE_BLOCKED",
                "reason": rule_decision.reason,
                "matched_rule_id": rule_decision.matched_rule_id,
            },
        )
        session.flush()
        raise NeuroConflictError(
            rule_decision.reason or "target blocked by channel rule",
            error_code="CHANNEL_RULE_BLOCKED",
        )
    accounts = repository.list_campaign_accounts(session, campaign_id=campaign.id)
    selected = AccountSelector(session=session).select_account(campaign, accounts, target)
    analytics = AnalyticsService()
    analytics.write_event(
        session,
        workspace_id=workspace_id,
        campaign_id=campaign.id,
        account_id=selected.account.account_id if selected.account is not None else None,
        target_id=target.id,
        observed_post_id=observed_post.id,
        event_type="ai_generation_started",
        message="AI neuro-comment generation started",
        data={},
    )
    prompt = PromptBuilder().build(campaign=campaign, observed_post=observed_post)
    try:
        from app.modules.neuro_commenting import job_handlers

        generated = job_handlers.build_ai_comment_generator().generate(prompt)
    except AICommentGenerationError as exc:
        observed_post.status = NeuroObservedPostStatus.FAILED.value
        observed_post.processed_at = utc_now()
        analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            account_id=selected.account.account_id if selected.account is not None else None,
            target_id=target.id,
            observed_post_id=observed_post.id,
            event_type="ai_generation_failed",
            event_level=NeuroEventLevel.ERROR,
            message="AI neuro-comment generation failed",
            data={"error_code": exc.error_code, "error_class": exc.__class__.__name__},
        )
        session.flush()
        raise
    safety = SafetyPolicy().check(
        text=generated.text,
        campaign=CampaignSafetySnapshot(status=campaign.status),
        target=TargetSafetySnapshot(status=target.status),
        account=AccountSafetySnapshot(status=selected.account.status)
        if selected.account is not None
        else None,
    )
    comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        account_id=selected.account.account_id if selected.account is not None else None,
        observed_post_id=observed_post.id,
        generated_text=generated.text,
        final_text=generated.text,
        model=generated.model,
        provider=generated.provider,
        prompt_version=prompt.prompt_version,
        language=observed_post.language,
        safety_status=safety.status.value,
        safety_reason=safety.reason,
        approval_status=NeuroGeneratedApprovalStatus.PENDING.value,
    )
    observed_post.status = NeuroObservedPostStatus.GENERATED.value
    observed_post.processed_at = utc_now()
    session.add(comment)
    session.flush()
    analytics.record_generated_comment(session, campaign=campaign, target=target, comment=comment)
    analytics.write_event(
        session,
        workspace_id=workspace_id,
        campaign_id=campaign.id,
        account_id=comment.account_id,
        target_id=target.id,
        observed_post_id=observed_post.id,
        generated_comment_id=comment.id,
        event_type="ai_generation_completed",
        message="AI neuro-comment generated and awaiting manual approval",
        data={
            "provider": generated.provider,
            "model": generated.model,
            "prompt_tokens": generated.prompt_tokens,
            "completion_tokens": generated.completion_tokens,
            "total_tokens": generated.total_tokens,
            "auto_send": False,
        },
    )
    analytics.write_event(
        session,
        workspace_id=workspace_id,
        campaign_id=campaign.id,
        account_id=comment.account_id,
        target_id=target.id,
        observed_post_id=observed_post.id,
        generated_comment_id=comment.id,
        event_type="comment_generated",
        message="neuro comment generated and awaiting manual approval",
        data={"provider": generated.provider, "model": generated.model, "auto_send": False},
    )
    return comment


def run_generate_comment(
    campaign_id: str, workspace_id: str, observed_post_id: str, force: bool = False
) -> str:
    from app.modules.neuro_commenting import job_handlers

    with job_handlers.SessionLocal() as session:
        try:
            comment = generate_comment(
                session,
                campaign_id=campaign_id,
                workspace_id=workspace_id,
                observed_post_id=observed_post_id,
                force=force,
            )
            session.commit()
            return comment.id
        except AICommentGenerationError:
            session.commit()
            raise
