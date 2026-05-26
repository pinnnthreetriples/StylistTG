from __future__ import annotations


from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import (
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
    NeuroCommentTarget,
    new_id,
    utc_now,
)
from app.services.neuro_commenting.account_selector import AccountSelector
from app.services.neuro_commenting.ai_comment_generator import (
    AICommentGenerationError,
    build_ai_comment_generator,
)
from app.services.neuro_commenting.analytics_service import AnalyticsService
from app.services.neuro_commenting.enums import (
    NeuroCampaignStatus,
    NeuroEventLevel,
    NeuroGeneratedApprovalStatus,
    NeuroObservedPostStatus,
    NeuroTargetStatus,
)
from app.services.neuro_commenting.errors import (
    NeuroCommentingError,
    NeuroConflictError,
    NeuroNotFoundError,
    NeuroRuntimeUnavailableError,
)
from app.services.neuro_commenting.discussion_resolver import (
    DiscussionMessageResolver,
    build_discussion_message_resolver,
)
from app.services.neuro_commenting.post_detector import PostDetector
from app.services.neuro_commenting.prompt_builder import PromptBuilder
from app.services.neuro_commenting.rules_policy import ChannelRulesPolicy
from app.services.neuro_commenting.safety_policy import SafetyPolicy
from app.services.neuro_commenting import repository
from app.services.neuro_commenting.tdlib_observer import (
    TelegramPostObserver,
    build_telegram_post_observer,
)


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
    rule_decision = ChannelRulesPolicy().check_target_allowed(
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
        generated = build_ai_comment_generator().generate(prompt)
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
        campaign=campaign,
        target=target,
        account=selected.account,
        session=session,
        workspace_id=workspace_id,
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
    with SessionLocal() as session:
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


def observe_campaign(
    session: Session,
    *,
    campaign_id: str,
    workspace_id: str,
    limit: int | None = None,
    generate: bool = True,
    observer: TelegramPostObserver | None = None,
    resolver: DiscussionMessageResolver | None = None,
) -> list[NeuroCommentObservedPost]:
    campaign = _require_campaign_for_job(
        session, campaign_id=campaign_id, workspace_id=workspace_id
    )
    _require_observable_campaign(campaign.status)
    analytics = AnalyticsService()
    analytics.write_event(
        session,
        workspace_id=workspace_id,
        campaign_id=campaign.id,
        event_type="observe_campaign_started",
        message="neuro-comment campaign observation started",
        data={"limit": limit, "generate": generate},
    )
    created: list[NeuroCommentObservedPost] = []
    page = 1
    page_limit = 100
    while True:
        targets, total = repository.list_targets(
            session, campaign_id=campaign.id, page=page, limit=page_limit
        )
        if not targets:
            break
        for target in targets:
            if target.status != NeuroTargetStatus.ACTIVE.value:
                continue
            try:
                created.extend(
                    observe_target(
                        session,
                        campaign_id=campaign.id,
                        target_id=target.id,
                        workspace_id=workspace_id,
                        limit=limit,
                        generate=generate,
                        observer=observer,
                        resolver=resolver,
                    )
                )
            except NeuroCommentingError:
                continue
            except Exception as exc:
                _write_observe_failed(
                    session,
                    workspace_id=workspace_id,
                    campaign_id=campaign.id,
                    target_id=target.id,
                    account_id=None,
                    error_code="OBSERVE_FAILED",
                    error_class=exc.__class__.__name__,
                )
                continue
        if page * page_limit >= total:
            break
        page += 1
    return created


def observe_target(
    session: Session,
    *,
    campaign_id: str,
    target_id: str,
    workspace_id: str,
    limit: int | None = None,
    generate: bool = True,
    observer: TelegramPostObserver | None = None,
    resolver: DiscussionMessageResolver | None = None,
) -> list[NeuroCommentObservedPost]:
    campaign = _require_campaign_for_job(
        session, campaign_id=campaign_id, workspace_id=workspace_id
    )
    _require_observable_campaign(campaign.status)
    target = repository.require_target(session, target_id=target_id, campaign_id=campaign.id)
    if target.status != NeuroTargetStatus.ACTIVE.value:
        _write_observe_failed(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            target_id=target.id,
            account_id=None,
            error_code="TARGET_NOT_ACTIVE",
            error_class="NeuroConflictError",
        )
        raise NeuroConflictError("target is not active", error_code="TARGET_NOT_ACTIVE")
    decision = ChannelRulesPolicy().check_target_allowed(
        session,
        workspace_id=workspace_id,
        target=target,
    )
    if not decision.allowed:
        _write_observe_failed(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            target_id=target.id,
            account_id=None,
            error_code="CHANNEL_RULE_BLOCKED",
            error_class="ChannelRulesPolicy",
        )
        AnalyticsService().write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            target_id=target.id,
            event_type="channel_rule_blocked",
            event_level=NeuroEventLevel.WARNING,
            message="channel rule blocked neuro-comment observation",
            data={
                "error_code": "CHANNEL_RULE_BLOCKED",
                "reason": decision.reason,
                "matched_rule_id": decision.matched_rule_id,
            },
        )
        session.flush()
        return []
    accounts = repository.list_campaign_accounts(session, campaign_id=campaign.id)
    selected = AccountSelector(session=session).select_account(campaign, accounts, target)
    if selected.account is None:
        _write_observe_failed(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            target_id=target.id,
            account_id=None,
            error_code="NO_ACTIVE_ACCOUNT",
            error_class="NeuroConflictError",
        )
        raise NeuroConflictError("no active account", error_code="NO_ACTIVE_ACCOUNT")
    active_observer = observer or build_telegram_post_observer()
    post_limit = limit or settings.neuro_comment_observe_post_limit
    analytics = AnalyticsService()
    analytics.write_event(
        session,
        workspace_id=workspace_id,
        campaign_id=campaign.id,
        account_id=selected.account.account_id,
        target_id=target.id,
        event_type="observe_target_started",
        message="neuro-comment target observation started",
        data={"limit": post_limit, "generate": generate},
    )
    metadata_missing = not target.channel_id or not target.discussion_chat_id
    if metadata_missing:
        try:
            target = refresh_target_metadata(
                session,
                campaign_id=campaign.id,
                target_id=target.id,
                workspace_id=workspace_id,
                observer=active_observer,
            )
        except NeuroCommentingError as exc:
            _write_observe_failed(
                session,
                workspace_id=workspace_id,
                campaign_id=campaign.id,
                target_id=target.id,
                account_id=selected.account.account_id,
                error_code=exc.error_code,
                error_class=exc.__class__.__name__,
            )
            raise
    if target.status == NeuroTargetStatus.NO_DISCUSSION.value or not target.discussion_chat_id:
        _write_observe_failed(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            target_id=target.id,
            account_id=selected.account.account_id,
            error_code="TARGET_NO_DISCUSSION",
            error_class="NeuroConflictError",
        )
        session.flush()
        return []
    try:
        posts = active_observer.fetch_recent_posts(selected.account.account_id, target, post_limit)
    except NeuroCommentingError as exc:
        _write_observe_failed(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            target_id=target.id,
            account_id=selected.account.account_id,
            error_code=exc.error_code,
            error_class=exc.__class__.__name__,
        )
        raise
    detector = PostDetector(random_seed=target.id)
    created: list[NeuroCommentObservedPost] = []
    for post in posts:
        existing = repository.get_observed_post_by_message(
            session,
            target_id=target.id,
            source_chat_id=post.source_chat_id,
            source_message_id=post.source_message_id,
        )
        if existing is not None:
            analytics.write_event(
                session,
                workspace_id=workspace_id,
                campaign_id=campaign.id,
                account_id=selected.account.account_id,
                target_id=target.id,
                event_type="post_skipped",
                message="telegram post already observed",
                data={"error_code": "POST_ALREADY_OBSERVED", "target_id": target.id},
            )
            continue
        decision = detector.match(
            mode=campaign.mode,
            post_text=post.post_text,
            keywords=target.keywords,
            exclude_keywords=target.exclude_keywords,
        )
        if not decision.matched:
            analytics.write_event(
                session,
                workspace_id=workspace_id,
                campaign_id=campaign.id,
                account_id=selected.account.account_id,
                target_id=target.id,
                event_type="post_skipped",
                message="telegram post did not match campaign rules",
                data={"error_code": "POST_NOT_MATCHED", "reason": decision.reason},
            )
            continue
        observed, was_created = repository.create_or_get_observed_post(
            session,
            campaign_id=campaign.id,
            target_id=target.id,
            source_chat_id=post.source_chat_id,
            source_message_id=post.source_message_id,
            post_text=post.post_text,
            media_summary=post.media_summary,
            language=post.language,
            matched_mode=decision.matched_mode,
            matched_keywords=decision.matched_keywords,
        )
        if not was_created:
            continue
        _resolve_discussion_for_observed_post(
            session,
            workspace_id=workspace_id,
            account_id=selected.account.account_id,
            target=target,
            observed=observed,
            resolver=resolver,
            analytics=analytics,
        )
        target.last_seen_message_id = post.source_message_id
        created.append(observed)
        analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            account_id=selected.account.account_id,
            target_id=target.id,
            observed_post_id=observed.id,
            event_type="post_observed",
            message="telegram post observed",
            data={"target_id": target.id},
        )
        if generate:
            analytics.write_event(
                session,
                workspace_id=workspace_id,
                campaign_id=campaign.id,
                account_id=selected.account.account_id,
                target_id=target.id,
                observed_post_id=observed.id,
                event_type="comment_generation_enqueued",
                message="comment generation requested for observed post",
                data={},
            )
            try:
                generate_comment(
                    session,
                    campaign_id=campaign.id,
                    workspace_id=workspace_id,
                    observed_post_id=observed.id,
                )
            except AICommentGenerationError:
                continue
    session.flush()
    return created


def resolve_observed_post_discussion(
    session: Session,
    *,
    observed_post_id: str,
    workspace_id: str,
    resolver: DiscussionMessageResolver | None = None,
) -> NeuroCommentObservedPost:
    observed = repository.require_observed_post_for_workspace(
        session, observed_post_id=observed_post_id, workspace_id=workspace_id
    )
    campaign = _require_campaign_for_job(
        session, campaign_id=observed.campaign_id, workspace_id=workspace_id
    )
    target = repository.require_target(
        session, target_id=observed.target_id, campaign_id=campaign.id
    )
    accounts = repository.list_campaign_accounts(session, campaign_id=campaign.id)
    selected = AccountSelector(session=session).select_account(campaign, accounts, target)
    if selected.account is None:
        raise NeuroConflictError("no active account", error_code="NO_ACTIVE_ACCOUNT")
    _resolve_discussion_for_observed_post(
        session,
        workspace_id=workspace_id,
        account_id=selected.account.account_id,
        target=target,
        observed=observed,
        resolver=resolver,
        analytics=AnalyticsService(),
    )
    session.flush()
    return observed


def _resolve_discussion_for_observed_post(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    target: NeuroCommentTarget,
    observed: NeuroCommentObservedPost,
    resolver: DiscussionMessageResolver | None,
    analytics: AnalyticsService,
) -> None:
    active_resolver = resolver or build_discussion_message_resolver()
    resolution = active_resolver.resolve(
        account_id=account_id,
        target=target,
        source_chat_id=observed.source_chat_id,
        source_message_id=observed.source_message_id,
    )
    now = utc_now()
    observed.discussion_chat_id = resolution.discussion_chat_id
    observed.discussion_message_id = resolution.discussion_message_id
    observed.discussion_resolution_error_code = resolution.error_code
    observed.discussion_resolved_at = now if resolution.discussion_message_id else None
    if resolution.discussion_message_id:
        analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=observed.campaign_id,
            account_id=account_id,
            target_id=target.id,
            observed_post_id=observed.id,
            event_type="discussion_message_resolved",
            message="discussion message resolved for observed post",
            data={"target_id": target.id, "observed_post_id": observed.id},
        )
    else:
        analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=observed.campaign_id,
            account_id=account_id,
            target_id=target.id,
            observed_post_id=observed.id,
            event_type="discussion_message_resolution_failed",
            event_level=NeuroEventLevel.WARNING,
            message="discussion message could not be resolved",
            data={
                "target_id": target.id,
                "observed_post_id": observed.id,
                "error_code": resolution.error_code or "DISCUSSION_MESSAGE_NOT_RESOLVED",
            },
        )


def refresh_target_metadata(
    session: Session,
    *,
    campaign_id: str,
    target_id: str,
    workspace_id: str,
    observer: TelegramPostObserver | None = None,
) -> NeuroCommentTarget:
    campaign = _require_campaign_for_job(
        session, campaign_id=campaign_id, workspace_id=workspace_id
    )
    target = repository.require_target(session, target_id=target_id, campaign_id=campaign.id)
    accounts = repository.list_campaign_accounts(session, campaign_id=campaign.id)
    selected = AccountSelector(session=session).select_account(campaign, accounts, target)
    if selected.account is None:
        raise NeuroConflictError("no active account", error_code="NO_ACTIVE_ACCOUNT")
    analytics = AnalyticsService()
    analytics.write_event(
        session,
        workspace_id=workspace_id,
        campaign_id=campaign.id,
        account_id=selected.account.account_id,
        target_id=target.id,
        event_type="target_metadata_refresh_started",
        message="target metadata refresh started",
        data={"target_id": target.id},
    )
    try:
        metadata = (observer or build_telegram_post_observer()).refresh_target_metadata(
            selected.account.account_id, target
        )
    except NeuroRuntimeUnavailableError:
        analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=campaign.id,
            account_id=selected.account.account_id,
            target_id=target.id,
            event_type="target_metadata_refresh_failed",
            event_level=NeuroEventLevel.ERROR,
            message="target metadata refresh failed",
            data={"error_code": "TDLIB_RUNTIME_UNAVAILABLE"},
        )
        raise
    target.channel_id = metadata.channel_id
    target.discussion_chat_id = metadata.discussion_chat_id
    target.title = metadata.title
    target.username = metadata.username
    if metadata.status == NeuroTargetStatus.NO_DISCUSSION.value or not metadata.discussion_chat_id:
        target.status = NeuroTargetStatus.NO_DISCUSSION.value
        event_type = "target_no_discussion"
        message = "target discussion is unavailable"
    else:
        target.status = metadata.status or NeuroTargetStatus.ACTIVE.value
        event_type = "target_metadata_refreshed"
        message = "target metadata refreshed"
    analytics.write_event(
        session,
        workspace_id=workspace_id,
        campaign_id=campaign.id,
        account_id=selected.account.account_id,
        target_id=target.id,
        event_type=event_type,
        message=message,
        data={"target_id": target.id},
    )
    session.flush()
    return target


def _require_observable_campaign(status: str) -> None:
    if status not in {NeuroCampaignStatus.RUNNING.value, NeuroCampaignStatus.READY.value}:
        raise NeuroConflictError("campaign is not observable", error_code="CAMPAIGN_NOT_OBSERVABLE")


def _require_campaign_for_job(session: Session, *, campaign_id: str, workspace_id: str):
    campaign = repository.get_campaign(session, campaign_id=campaign_id, workspace_id=workspace_id)
    if campaign is None:
        raise NeuroNotFoundError("campaign not found", error_code="CAMPAIGN_NOT_FOUND")
    return campaign


def run_observe_campaign(
    campaign_id: str, workspace_id: str, limit: int | None, generate: bool
) -> list[str]:
    with SessionLocal() as session:
        try:
            posts = observe_campaign(
                session,
                campaign_id=campaign_id,
                workspace_id=workspace_id,
                limit=limit,
                generate=generate,
            )
            session.commit()
            return [post.id for post in posts]
        except Exception:
            session.commit()
            raise


def run_observe_target(
    campaign_id: str, target_id: str, workspace_id: str, limit: int | None, generate: bool
) -> list[str]:
    with SessionLocal() as session:
        try:
            posts = observe_target(
                session,
                campaign_id=campaign_id,
                target_id=target_id,
                workspace_id=workspace_id,
                limit=limit,
                generate=generate,
            )
            session.commit()
            return [post.id for post in posts]
        except Exception:
            session.commit()
            raise


def run_refresh_target_metadata(campaign_id: str, target_id: str, workspace_id: str) -> str:
    with SessionLocal() as session:
        target = refresh_target_metadata(
            session,
            campaign_id=campaign_id,
            target_id=target_id,
            workspace_id=workspace_id,
        )
        session.commit()
        return target.id


def prepare_send(*args: object, **kwargs: object) -> None:
    raise NeuroCommentJobNotImplementedError("prepare_send is planned for a later phase")


def send_comment(*args: object, **kwargs: object) -> None:
    raise NeuroCommentJobNotImplementedError("send_comment is disabled in foundation skeleton")


def run_send_attempt(attempt_id: str, workspace_id: str) -> str:
    from app.services.neuro_commenting.sender_service import SenderService

    with SessionLocal() as session:
        attempt = SenderService().send_attempt(
            session,
            attempt_id=attempt_id,
            workspace_id=workspace_id,
        )
        session.commit()
        return attempt.id


def reconcile_attempt(*args: object, **kwargs: object) -> None:
    raise NeuroCommentJobNotImplementedError("reconcile_attempt is planned for a later phase")


def refresh_target_health(*args: object, **kwargs: object) -> None:
    raise NeuroCommentJobNotImplementedError("refresh_target_health is planned for a later phase")


def _write_observe_failed(
    session: Session,
    *,
    workspace_id: str,
    campaign_id: str,
    target_id: str | None,
    account_id: str | None,
    error_code: str,
    error_class: str,
) -> None:
    AnalyticsService().write_event(
        session,
        workspace_id=workspace_id,
        campaign_id=campaign_id,
        account_id=account_id,
        target_id=target_id,
        event_type="observe_failed",
        event_level=NeuroEventLevel.ERROR,
        message="neuro-comment observation failed",
        data={"error_code": error_code, "error_class": error_class},
    )
