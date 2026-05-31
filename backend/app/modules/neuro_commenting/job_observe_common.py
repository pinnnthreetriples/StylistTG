from __future__ import annotations

# pyright: reportUnusedFunction=false


from sqlalchemy.orm import Session

from app.models import (
    NeuroCommentObservedPost,
    NeuroCommentTarget,
    utc_now,
)
from app.modules.neuro_commenting.account_selector import AccountSelector
from app.modules.neuro_commenting.analytics_service import AnalyticsService
from app.modules.neuro_commenting.enums import (
    NeuroCampaignStatus,
    NeuroEventLevel,
    NeuroTargetStatus,
)
from app.modules.neuro_commenting.errors import (
    NeuroConflictError,
    NeuroNotFoundError,
    NeuroRuntimeUnavailableError,
)
from app.modules.neuro_commenting.discussion_resolver import (
    DiscussionMessageResolver,
    build_discussion_message_resolver,
)
from app.modules.neuro_commenting import repository
from app.modules.neuro_commenting.tdlib_observer import (
    TelegramPostObserver,
    build_telegram_post_observer,
)


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
