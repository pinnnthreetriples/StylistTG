from __future__ import annotations

from uuid import UUID
from fastapi import Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import (
    NeuroAccountStatsPageRead,
    NeuroAccountStatsRead,
    NeuroAttemptPageRead,
    NeuroAttemptRead,
    NeuroCampaignCreate,
    NeuroCampaignPageRead,
    NeuroCampaignRead,
    NeuroCampaignStatsRead,
    NeuroCampaignUpdate,
    NeuroChannelStatsPageRead,
    NeuroChannelStatsRead,
    NeuroFailureReasonPageRead,
    NeuroFailureReasonRead,
    NeuroLiveReadinessRead,
)
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated
from app.modules.auth.dependencies import require_mutation_permission
from app.modules.neuro_commenting import repository
from app.modules.neuro_commenting.analytics_service import AnalyticsService
from app.modules.neuro_commenting.campaign_service import CampaignService
from app.modules.neuro_commenting.live_readiness_service import LiveReadinessService

from .router_base import router
from .router_common import (
    _neuro_error,
    _reject_unknown_list_query_params,
)

@router.post("/campaigns", response_model=NeuroCampaignRead, status_code=status.HTTP_201_CREATED)
def post_campaign(
    payload: NeuroCampaignCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroCampaignRead:
    try:
        campaign = CampaignService().create_campaign(
            session,
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
            payload=payload.model_dump(),
        )
        session.commit()
        session.refresh(campaign)
        return NeuroCampaignRead.model_validate(campaign)
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc
@router.get("/campaigns", response_model=NeuroCampaignPageRead)
def get_campaigns(
    page: int = Query(default=1, ge=1, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
    _valid_query: None = Depends(_reject_unknown_list_query_params),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroCampaignPageRead:
    items, total = repository.list_campaigns(
        session, workspace_id=auth.workspace_id, page=page, limit=limit
    )
    return NeuroCampaignPageRead(
        items=[NeuroCampaignRead.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/campaigns/{campaign_id}", response_model=NeuroCampaignRead)
def get_campaign(
    campaign_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroCampaignRead:
    try:
        campaign = repository.require_campaign(
            session, campaign_id=str(campaign_id), workspace_id=auth.workspace_id
        )
        return NeuroCampaignRead.model_validate(campaign)
    except ValueError as exc:
        raise _neuro_error(exc) from exc


@router.get("/campaigns/{campaign_id}/stats", response_model=NeuroCampaignStatsRead)
def get_campaign_stats(
    campaign_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroCampaignStatsRead:
    try:
        repository.require_campaign(
            session, campaign_id=str(campaign_id), workspace_id=auth.workspace_id
        )
    except ValueError as exc:
        raise _neuro_error(exc) from exc
    return NeuroCampaignStatsRead.model_validate(
        AnalyticsService().campaign_stats(session, campaign_id=str(campaign_id))
    )


@router.get(
    "/campaigns/{campaign_id}/live-readiness",
    response_model=NeuroLiveReadinessRead,
)
def get_campaign_live_readiness(
    campaign_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroLiveReadinessRead:
    try:
        return LiveReadinessService().check(
            session, campaign_id=str(campaign_id), workspace_id=auth.workspace_id
        )
    except ValueError as exc:
        raise _neuro_error(exc) from exc


@router.get("/campaigns/{campaign_id}/account-stats", response_model=NeuroAccountStatsPageRead)
def get_campaign_account_stats(
    campaign_id: UUID,
    page: int = Query(default=1, ge=1, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
    _valid_query: None = Depends(_reject_unknown_list_query_params),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroAccountStatsPageRead:
    try:
        repository.require_campaign(
            session, campaign_id=str(campaign_id), workspace_id=auth.workspace_id
        )
    except ValueError as exc:
        raise _neuro_error(exc) from exc
    items, total = AnalyticsService().account_stats_page(
        session, campaign_id=str(campaign_id), page=page, limit=limit
    )
    return NeuroAccountStatsPageRead(
        items=[NeuroAccountStatsRead.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/campaigns/{campaign_id}/channel-stats", response_model=NeuroChannelStatsPageRead)
def get_campaign_channel_stats(
    campaign_id: UUID,
    page: int = Query(default=1, ge=1, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
    _valid_query: None = Depends(_reject_unknown_list_query_params),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroChannelStatsPageRead:
    try:
        campaign = repository.require_campaign(
            session, campaign_id=str(campaign_id), workspace_id=auth.workspace_id
        )
    except ValueError as exc:
        raise _neuro_error(exc) from exc
    items, total = AnalyticsService().channel_stats_page(
        session, campaign=campaign, page=page, limit=limit
    )
    return NeuroChannelStatsPageRead(
        items=[NeuroChannelStatsRead.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/campaigns/{campaign_id}/attempts", response_model=NeuroAttemptPageRead)
def get_campaign_attempts(
    campaign_id: UUID,
    page: int = Query(default=1, ge=1, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
    _valid_query: None = Depends(_reject_unknown_list_query_params),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroAttemptPageRead:
    try:
        repository.require_campaign(
            session, campaign_id=str(campaign_id), workspace_id=auth.workspace_id
        )
    except ValueError as exc:
        raise _neuro_error(exc) from exc
    items, total = AnalyticsService().attempts_page(
        session, campaign_id=str(campaign_id), page=page, limit=limit
    )
    return NeuroAttemptPageRead(
        items=[NeuroAttemptRead.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/campaigns/{campaign_id}/failure-reasons",
    response_model=NeuroFailureReasonPageRead,
)
def get_campaign_failure_reasons(
    campaign_id: UUID,
    page: int = Query(default=1, ge=1, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
    _valid_query: None = Depends(_reject_unknown_list_query_params),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroFailureReasonPageRead:
    try:
        repository.require_campaign(
            session, campaign_id=str(campaign_id), workspace_id=auth.workspace_id
        )
    except ValueError as exc:
        raise _neuro_error(exc) from exc
    items, total = AnalyticsService().failure_reasons(
        session, campaign_id=str(campaign_id), page=page, limit=limit
    )
    return NeuroFailureReasonPageRead(
        items=[NeuroFailureReasonRead.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.patch("/campaigns/{campaign_id}", response_model=NeuroCampaignRead)
def patch_campaign(
    campaign_id: UUID,
    payload: NeuroCampaignUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroCampaignRead:
    try:
        campaign = CampaignService().update_campaign(
            session,
            campaign_id=str(campaign_id),
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
            payload=payload.model_dump(exclude_unset=True),
        )
        session.commit()
        session.refresh(campaign)
        return NeuroCampaignRead.model_validate(campaign)
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc
