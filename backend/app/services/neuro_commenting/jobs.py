from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import NeuroCommentGeneratedComment, new_id
from app.services.neuro_commenting.account_selector import AccountSelector
from app.services.neuro_commenting.ai_comment_generator import AICommentGenerator
from app.services.neuro_commenting.analytics_service import AnalyticsService
from app.services.neuro_commenting.enums import (
    NeuroGeneratedApprovalStatus,
    NeuroObservedPostStatus,
)
from app.services.neuro_commenting.prompt_builder import PromptBuilder
from app.services.neuro_commenting.safety_policy import SafetyPolicy
from app.services.neuro_commenting import repository


class NeuroCommentJobNotImplementedError(RuntimeError):
    pass


def generate_comment(
    session: Session,
    *,
    campaign_id: str,
    workspace_id: str,
    observed_post_id: str,
) -> NeuroCommentGeneratedComment:
    campaign = repository.require_campaign(
        session, campaign_id=campaign_id, workspace_id=workspace_id
    )
    observed_post = repository.get_observed_post(
        session, observed_post_id=observed_post_id, campaign_id=campaign.id
    )
    if observed_post is None:
        raise ValueError("observed post not found")
    target = repository.require_target(
        session, target_id=observed_post.target_id, campaign_id=campaign.id
    )
    accounts = repository.list_campaign_accounts(session, campaign_id=campaign.id)
    selected = AccountSelector().select_account(campaign, accounts, target)
    prompt = PromptBuilder().build(campaign=campaign, observed_post=observed_post)
    generated = AICommentGenerator().generate(prompt)
    safety = SafetyPolicy().check(
        text=generated.text,
        campaign=campaign,
        target=target,
        account=selected.account,
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
    observed_post.processed_at = datetime.now(UTC)
    session.add(comment)
    session.flush()
    analytics = AnalyticsService()
    analytics.record_generated_comment(session, campaign=campaign, target=target, comment=comment)
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


def run_generate_comment(campaign_id: str, workspace_id: str, observed_post_id: str) -> str:
    with SessionLocal() as session:
        comment = generate_comment(
            session,
            campaign_id=campaign_id,
            workspace_id=workspace_id,
            observed_post_id=observed_post_id,
        )
        session.commit()
        return comment.id


def observe_post(*args: object, **kwargs: object) -> None:
    raise NeuroCommentJobNotImplementedError("observe_post is planned for a later phase")


def prepare_send(*args: object, **kwargs: object) -> None:
    raise NeuroCommentJobNotImplementedError("prepare_send is planned for a later phase")


def send_comment(*args: object, **kwargs: object) -> None:
    raise NeuroCommentJobNotImplementedError("send_comment is disabled in foundation skeleton")


def reconcile_attempt(*args: object, **kwargs: object) -> None:
    raise NeuroCommentJobNotImplementedError("reconcile_attempt is planned for a later phase")


def refresh_target_health(*args: object, **kwargs: object) -> None:
    raise NeuroCommentJobNotImplementedError("refresh_target_health is planned for a later phase")
