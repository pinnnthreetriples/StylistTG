from __future__ import annotations


from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    NeuroCommentObservedPost,
)
from app.modules.neuro_commenting.account_selector import AccountSelector
from app.modules.neuro_commenting.analytics_service import AnalyticsService
from app.modules.neuro_commenting.enums import (
    NeuroTargetStatus,
)
from app.modules.neuro_commenting.errors import (
    NeuroCommentingError,
    NeuroConflictError,
)
from app.modules.neuro_commenting.discussion_resolver import (
    DiscussionMessageResolver,
)
from app.modules.neuro_commenting import repository
from app.modules.neuro_commenting.tdlib_observer import (
    TelegramPostObserver,
)


from app.modules.neuro_commenting.job_observe_common import (
    _require_campaign_for_job,
    _require_observable_campaign,
    _resolve_discussion_for_observed_post,
    _write_observe_failed,
    refresh_target_metadata,
)
from app.modules.neuro_commenting.job_observe_target import observe_target

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
