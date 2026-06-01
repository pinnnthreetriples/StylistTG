from __future__ import annotations

# pyright: reportPrivateUsage=false

from uuid import UUID
from fastapi import Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.contracts.queues import NEURO_COMMENT_QUEUE_NAME
from app.schemas import (
    NeuroAcceptedJobRead,
    NeuroGenerateObservedPostRequest,
    NeuroObserveCampaignRequest,
    NeuroObserveTargetRequest,
    NeuroObservedPostPageRead,
    NeuroObservedPostRead,
)
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated
from app.modules.auth.dependencies import require_mutation_permission
from app.modules.neuro_commenting import repository
from app.modules.neuro_commenting.analytics_service import AnalyticsService
from app.modules.neuro_commenting.enums import NeuroEventLevel
from app.modules.neuro_commenting.errors import NeuroCommentingError
from app.modules.neuro_commenting.jobs import resolve_observed_post_discussion

from .router_base import router
from .router_common import (
    _neuro_domain_error,
    _neuro_error,
    _raise_queue_unavailable,
    _reject_unknown_observed_query_params,
    _runtime_api,
)


@router.get("/observed-posts", response_model=NeuroObservedPostPageRead)
def get_observed_posts(
    campaign_id: UUID | None = Query(default=None),
    target_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
    _valid_query: None = Depends(_reject_unknown_observed_query_params),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroObservedPostPageRead:
    try:
        if campaign_id is not None:
            repository.require_campaign(
                session, campaign_id=str(campaign_id), workspace_id=auth.workspace_id
            )
    except ValueError as exc:
        raise _neuro_error(exc) from exc
    items, total = repository.list_observed_posts(
        session,
        workspace_id=auth.workspace_id,
        campaign_id=str(campaign_id) if campaign_id is not None else None,
        target_id=str(target_id) if target_id is not None else None,
        page=page,
        limit=limit,
    )
    return NeuroObservedPostPageRead(
        items=[NeuroObservedPostRead.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/observed-posts/{observed_post_id}", response_model=NeuroObservedPostRead)
def get_observed_post(
    observed_post_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroObservedPostRead:
    try:
        observed = repository.require_observed_post_for_workspace(
            session, observed_post_id=str(observed_post_id), workspace_id=auth.workspace_id
        )
        return NeuroObservedPostRead.model_validate(observed)
    except NeuroCommentingError as exc:
        raise _neuro_domain_error(exc) from exc


@router.post(
    "/campaigns/{campaign_id}/observe",
    response_model=NeuroAcceptedJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_observe_campaign(
    campaign_id: UUID,
    payload: NeuroObserveCampaignRequest | None = None,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroAcceptedJobRead:
    try:
        campaign = repository.require_campaign(
            session, campaign_id=str(campaign_id), workspace_id=auth.workspace_id
        )
    except ValueError as exc:
        raise _neuro_error(exc) from exc
    request = payload or NeuroObserveCampaignRequest()
    if not _runtime_api().enqueue_neuro_observe_campaign(
        campaign.id,
        auth.workspace_id,
        limit=request.limit,
        generate=request.generate,
    ):
        AnalyticsService().write_event(
            session,
            workspace_id=auth.workspace_id,
            campaign_id=campaign.id,
            event_type="observe_failed",
            event_level=NeuroEventLevel.ERROR,
            message="neuro-comment observe campaign enqueue failed",
            data={"error_code": "QUEUE_UNAVAILABLE"},
        )
        session.commit()
        _raise_queue_unavailable()
    return NeuroAcceptedJobRead(
        accepted=True,
        job_id=f"neuro-observe-campaign-{campaign.id}",
        queue_name=NEURO_COMMENT_QUEUE_NAME,
    )


@router.post(
    "/campaigns/{campaign_id}/targets/{target_id}/observe",
    response_model=NeuroAcceptedJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_observe_target(
    campaign_id: UUID,
    target_id: UUID,
    payload: NeuroObserveTargetRequest | None = None,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroAcceptedJobRead:
    try:
        campaign = repository.require_campaign(
            session, campaign_id=str(campaign_id), workspace_id=auth.workspace_id
        )
        repository.require_target(session, target_id=str(target_id), campaign_id=campaign.id)
    except ValueError as exc:
        raise _neuro_error(exc) from exc
    request = payload or NeuroObserveTargetRequest()
    if not _runtime_api().enqueue_neuro_observe_target(
        campaign.id,
        str(target_id),
        auth.workspace_id,
        limit=request.limit,
        generate=request.generate,
    ):
        AnalyticsService().write_event(
            session,
            workspace_id=auth.workspace_id,
            campaign_id=campaign.id,
            target_id=str(target_id),
            event_type="observe_failed",
            event_level=NeuroEventLevel.ERROR,
            message="neuro-comment observe target enqueue failed",
            data={"error_code": "QUEUE_UNAVAILABLE"},
        )
        session.commit()
        _raise_queue_unavailable()
    return NeuroAcceptedJobRead(
        accepted=True,
        job_id=f"neuro-observe-target-{target_id}",
        queue_name=NEURO_COMMENT_QUEUE_NAME,
    )


@router.post(
    "/campaigns/{campaign_id}/targets/{target_id}/refresh-metadata",
    response_model=NeuroAcceptedJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_refresh_target_metadata(
    campaign_id: UUID,
    target_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroAcceptedJobRead:
    try:
        campaign = repository.require_campaign(
            session, campaign_id=str(campaign_id), workspace_id=auth.workspace_id
        )
        repository.require_target(session, target_id=str(target_id), campaign_id=campaign.id)
    except ValueError as exc:
        raise _neuro_error(exc) from exc
    if not _runtime_api().enqueue_neuro_refresh_target_metadata(
        campaign.id, str(target_id), auth.workspace_id
    ):
        AnalyticsService().write_event(
            session,
            workspace_id=auth.workspace_id,
            campaign_id=campaign.id,
            target_id=str(target_id),
            event_type="target_metadata_refresh_failed",
            event_level=NeuroEventLevel.ERROR,
            message="target metadata refresh enqueue failed",
            data={"error_code": "QUEUE_UNAVAILABLE"},
        )
        session.commit()
        _raise_queue_unavailable()
    return NeuroAcceptedJobRead(
        accepted=True,
        job_id=f"neuro-refresh-target-{target_id}",
        queue_name=NEURO_COMMENT_QUEUE_NAME,
    )


@router.post(
    "/observed-posts/{observed_post_id}/generate",
    response_model=NeuroAcceptedJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_generate_observed_post(
    observed_post_id: UUID,
    payload: NeuroGenerateObservedPostRequest | None = None,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroAcceptedJobRead:
    request = payload or NeuroGenerateObservedPostRequest()
    try:
        observed = repository.require_observed_post_for_workspace(
            session, observed_post_id=str(observed_post_id), workspace_id=auth.workspace_id
        )
    except NeuroCommentingError as exc:
        raise _neuro_domain_error(exc) from exc
    job_id = _runtime_api().neuro_generate_comment_job_id(observed.id, force=request.force)
    if not _runtime_api().enqueue_neuro_generate_comment(
        observed.campaign_id,
        auth.workspace_id,
        observed.id,
        force=request.force,
        job_id=job_id,
    ):
        AnalyticsService().write_event(
            session,
            workspace_id=auth.workspace_id,
            campaign_id=observed.campaign_id,
            target_id=observed.target_id,
            observed_post_id=observed.id,
            event_type="ai_generation_failed",
            event_level=NeuroEventLevel.ERROR,
            message="AI neuro-comment generation enqueue failed",
            data={"error_code": "QUEUE_UNAVAILABLE"},
        )
        session.commit()
        _raise_queue_unavailable()
    return NeuroAcceptedJobRead(
        accepted=True,
        job_id=job_id,
        queue_name=NEURO_COMMENT_QUEUE_NAME,
    )


@router.post(
    "/observed-posts/{observed_post_id}/resolve-discussion",
    response_model=NeuroObservedPostRead,
)
def post_resolve_observed_post_discussion(
    observed_post_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroObservedPostRead:
    try:
        observed = resolve_observed_post_discussion(
            session,
            observed_post_id=str(observed_post_id),
            workspace_id=auth.workspace_id,
        )
        session.commit()
        session.refresh(observed)
        return NeuroObservedPostRead.model_validate(observed)
    except NeuroCommentingError as exc:
        session.commit()
        raise _neuro_domain_error(exc) from exc
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc
