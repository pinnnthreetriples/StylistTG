from __future__ import annotations


from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    NeuroCommentObservedPost,
)
from app.modules.neuro_commenting.account_selector import AccountSelector
from app.modules.neuro_commenting.ai_comment_generator import (
    AICommentGenerationError,
)
from app.modules.neuro_commenting.analytics_service import AnalyticsService
from app.modules.neuro_commenting.enums import (
    NeuroEventLevel,
    NeuroTargetStatus,
)
from app.modules.neuro_commenting.errors import (
    NeuroCommentingError,
    NeuroConflictError,
)
from app.modules.neuro_commenting.discussion_resolver import (
    DiscussionMessageResolver,
)
from app.modules.neuro_commenting.post_detector import PostDetector
from app.modules.neuro_commenting.channel_rules_service import ChannelRulesService
from app.modules.neuro_commenting import repository
from app.modules.neuro_commenting.tdlib_observer import (
    TelegramPostObserver,
    build_telegram_post_observer,
)


from app.modules.neuro_commenting.job_generate import generate_comment
from app.modules.neuro_commenting.job_observe_common import (
    _require_campaign_for_job,
    _require_observable_campaign,
    _resolve_discussion_for_observed_post,
    _write_observe_failed,
    refresh_target_metadata,
)

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
    decision = ChannelRulesService().evaluate_target_allowed(
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
