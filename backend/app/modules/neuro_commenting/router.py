from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.errors import AppError
from app.contracts.queues import NEURO_COMMENT_QUEUE_NAME
from app.schemas import (
    NeuroAcceptedJobRead,
    NeuroAccountStatsPageRead,
    NeuroAccountStatsRead,
    NeuroAttemptPageRead,
    NeuroAttemptRead,
    NeuroCampaignAccountCreate,
    NeuroCampaignAccountPageRead,
    NeuroCampaignAccountRead,
    NeuroCampaignCreate,
    NeuroCampaignPageRead,
    NeuroCampaignRead,
    NeuroCampaignStatsRead,
    NeuroCampaignUpdate,
    NeuroChannelRuleCreate,
    NeuroChannelRulePageRead,
    NeuroChannelRuleRead,
    NeuroChannelStatsPageRead,
    NeuroChannelStatsRead,
    NeuroEventPageRead,
    NeuroEventRead,
    NeuroGeneratedCommentPageRead,
    NeuroGeneratedCommentRead,
    NeuroGeneratedCommentRejectRequest,
    NeuroGeneratedCommentUpdate,
    NeuroFailureReasonPageRead,
    NeuroFailureReasonRead,
    NeuroGenerateObservedPostRequest,
    NeuroLimitCreate,
    NeuroLimitPageRead,
    NeuroLimitRead,
    NeuroLimitUpdate,
    NeuroLiveReadinessRead,
    NeuroManualSendRead,
    NeuroManualSendRequest,
    NeuroObservedPostPageRead,
    NeuroObservedPostRead,
    NeuroObserveCampaignRequest,
    NeuroObserveTargetRequest,
    NeuroPromptPresetListRead,
    NeuroPromptPresetRead,
    NeuroTargetBulkCreateRead,
    NeuroTargetBulkCreateRequest,
    NeuroTargetBulkSkippedItemRead,
    NeuroTargetCreate,
    NeuroTargetPageRead,
    NeuroTargetRead,
)
from app.config import settings
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import (
    require_authenticated,
    require_mutation_permission,
)
from app.services.neuro_commenting import repository
from app.services.neuro_commenting.analytics_service import AnalyticsService
from app.services.neuro_commenting.approval_service import ApprovalService
from app.services.neuro_commenting.campaign_account_service import CampaignAccountService
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.channel_rules_service import ChannelRulesService
from app.services.neuro_commenting.enums import NeuroAttemptStatus, NeuroEventLevel
from app.services.neuro_commenting.errors import NeuroCommentingError, NeuroConflictError
from app.services.neuro_commenting.limits_service import LimitsService
from app.services.neuro_commenting.live_readiness_service import LiveReadinessService
from app.services.neuro_commenting.prompt_presets import list_prompt_presets
from app.services.neuro_commenting.sender_service import SenderService
from app.services.neuro_commenting.target_service import TargetService
from app.services.neuro_commenting.jobs import resolve_observed_post_discussion
from app.job_queue.rq import (
    enqueue_neuro_generate_comment,
    enqueue_neuro_observe_campaign,
    enqueue_neuro_observe_target,
    enqueue_neuro_refresh_target_metadata,
    enqueue_neuro_send_attempt,
    neuro_generate_comment_job_id,
)

router = APIRouter(prefix="/api/neuro-commenting", tags=["neuro-commenting"])
_LIST_QUERY_PARAMS = {"page", "limit"}
_GENERATED_QUERY_PARAMS = {"campaign_id", "page", "limit"}
_OBSERVED_QUERY_PARAMS = {"campaign_id", "target_id", "page", "limit"}
_ATTEMPT_QUERY_PARAMS = {"campaign_id", "generated_comment_id", "page", "limit"}
_EVENT_QUERY_PARAMS = {"campaign_id", "page", "limit"}


def _reject_unknown_list_query_params(request: Request) -> None:
    _reject_unknown_query_params(request, allowed=_LIST_QUERY_PARAMS)


def _reject_unknown_generated_query_params(request: Request) -> None:
    _reject_unknown_query_params(request, allowed=_GENERATED_QUERY_PARAMS)


def _reject_unknown_observed_query_params(request: Request) -> None:
    _reject_unknown_query_params(request, allowed=_OBSERVED_QUERY_PARAMS)


def _reject_unknown_attempt_query_params(request: Request) -> None:
    _reject_unknown_query_params(request, allowed=_ATTEMPT_QUERY_PARAMS)


def _reject_unknown_event_query_params(request: Request) -> None:
    _reject_unknown_query_params(request, allowed=_EVENT_QUERY_PARAMS)


def _reject_unknown_query_params(request: Request, *, allowed: set[str]) -> None:
    unknown = set(request.query_params) - allowed
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"unknown query parameter: {sorted(unknown)[0]}",
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


@router.post(
    "/campaigns/{campaign_id}/accounts",
    response_model=NeuroCampaignAccountRead,
    status_code=status.HTTP_201_CREATED,
)
def post_campaign_account(
    campaign_id: UUID,
    payload: NeuroCampaignAccountCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroCampaignAccountRead:
    try:
        account = CampaignAccountService().add_account(
            session,
            campaign_id=str(campaign_id),
            account_id=payload.account_id,
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
            rotation_weight=payload.rotation_weight,
            rotation_order=payload.rotation_order,
        )
        session.commit()
        session.refresh(account)
        return NeuroCampaignAccountRead.model_validate(account)
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc


@router.delete(
    "/campaigns/{campaign_id}/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_campaign_account(
    campaign_id: UUID,
    account_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> None:
    try:
        CampaignAccountService().remove_account(
            session,
            campaign_id=str(campaign_id),
            account_id=str(account_id),
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc


@router.get(
    "/campaigns/{campaign_id}/accounts",
    response_model=NeuroCampaignAccountPageRead,
)
def get_campaign_accounts(
    campaign_id: UUID,
    page: int = Query(default=1, ge=1, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
    _valid_query: None = Depends(_reject_unknown_list_query_params),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroCampaignAccountPageRead:
    try:
        campaign = repository.require_campaign(
            session, campaign_id=str(campaign_id), workspace_id=auth.workspace_id
        )
    except ValueError as exc:
        raise _neuro_error(exc) from exc
    items, total = repository.list_campaign_accounts_page(
        session, campaign_id=campaign.id, page=page, limit=limit
    )
    return NeuroCampaignAccountPageRead(
        items=[NeuroCampaignAccountRead.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.post(
    "/campaigns/{campaign_id}/targets",
    response_model=NeuroTargetRead,
    status_code=status.HTTP_201_CREATED,
)
def post_campaign_target(
    campaign_id: UUID,
    payload: NeuroTargetCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroTargetRead:
    try:
        target = TargetService().add_target(
            session,
            campaign_id=str(campaign_id),
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
            payload=payload.model_dump(),
        )
        session.commit()
        session.refresh(target)
        return NeuroTargetRead.model_validate(target)
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc


@router.post(
    "/campaigns/{campaign_id}/targets/bulk",
    response_model=NeuroTargetBulkCreateRead,
    status_code=status.HTTP_200_OK,
)
def post_campaign_targets_bulk(
    campaign_id: UUID,
    payload: NeuroTargetBulkCreateRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroTargetBulkCreateRead:
    try:
        result = TargetService().bulk_add_targets(
            session,
            campaign_id=str(campaign_id),
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
            items=[item.model_dump() for item in payload.items],
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc
    return NeuroTargetBulkCreateRead(
        created=[NeuroTargetRead.model_validate(target) for target in result.created],
        skipped=[
            NeuroTargetBulkSkippedItemRead(channel_ref=item.channel_ref, reason=item.reason)
            for item in result.skipped
        ],
        requested=result.requested,
    )


@router.delete(
    "/campaigns/{campaign_id}/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_campaign_target(
    campaign_id: UUID,
    target_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> None:
    try:
        TargetService().remove_target(
            session,
            campaign_id=str(campaign_id),
            target_id=str(target_id),
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc


@router.get(
    "/campaigns/{campaign_id}/targets",
    response_model=NeuroTargetPageRead,
)
def get_campaign_targets(
    campaign_id: UUID,
    page: int = Query(default=1, ge=1, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
    _valid_query: None = Depends(_reject_unknown_list_query_params),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroTargetPageRead:
    try:
        campaign = repository.require_campaign(
            session, campaign_id=str(campaign_id), workspace_id=auth.workspace_id
        )
    except ValueError as exc:
        raise _neuro_error(exc) from exc
    items, total = repository.list_targets(session, campaign_id=campaign.id, page=page, limit=limit)
    return NeuroTargetPageRead(
        items=[NeuroTargetRead.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/campaigns/{campaign_id}/limits", response_model=NeuroLimitPageRead)
def get_campaign_limits(
    campaign_id: UUID,
    page: int = Query(default=1, ge=1, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
    _valid_query: None = Depends(_reject_unknown_list_query_params),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroLimitPageRead:
    try:
        items, total = LimitsService().list_limits(
            session,
            campaign_id=str(campaign_id),
            workspace_id=auth.workspace_id,
            page=page,
            limit=limit,
        )
    except ValueError as exc:
        raise _neuro_error(exc) from exc
    return NeuroLimitPageRead(
        items=[NeuroLimitRead.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.post(
    "/campaigns/{campaign_id}/limits",
    response_model=NeuroLimitRead,
    status_code=status.HTTP_201_CREATED,
)
def post_campaign_limit(
    campaign_id: UUID,
    payload: NeuroLimitCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroLimitRead:
    try:
        limit = LimitsService().create_limit(
            session,
            campaign_id=str(campaign_id),
            workspace_id=auth.workspace_id,
            payload=payload.model_dump(),
        )
        session.commit()
        session.refresh(limit)
        return NeuroLimitRead.model_validate(limit)
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc


@router.patch("/limits/{limit_id}", response_model=NeuroLimitRead)
def patch_limit(
    limit_id: UUID,
    payload: NeuroLimitUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroLimitRead:
    try:
        limit = LimitsService().update_limit(
            session,
            limit_id=str(limit_id),
            workspace_id=auth.workspace_id,
            payload=payload.model_dump(exclude_unset=True),
        )
        session.commit()
        session.refresh(limit)
        return NeuroLimitRead.model_validate(limit)
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc


@router.delete("/limits/{limit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_limit(
    limit_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> None:
    try:
        LimitsService().delete_limit(
            session, limit_id=str(limit_id), workspace_id=auth.workspace_id
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc


@router.get("/prompt-presets", response_model=NeuroPromptPresetListRead)
def get_prompt_presets(
    _auth: AuthContext = Depends(require_authenticated),
) -> NeuroPromptPresetListRead:
    items = [
        NeuroPromptPresetRead.model_validate(preset.to_dict()) for preset in list_prompt_presets()
    ]
    return NeuroPromptPresetListRead(items=items, total=len(items))


@router.get("/channel-rules", response_model=NeuroChannelRulePageRead)
def get_channel_rules(
    page: int = Query(default=1, ge=1, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
    _valid_query: None = Depends(_reject_unknown_list_query_params),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroChannelRulePageRead:
    items, total = ChannelRulesService().list_rules(
        session, workspace_id=auth.workspace_id, page=page, limit=limit
    )
    return NeuroChannelRulePageRead(
        items=[NeuroChannelRuleRead.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.post(
    "/channel-rules",
    response_model=NeuroChannelRuleRead,
    status_code=status.HTTP_201_CREATED,
)
def post_channel_rule(
    payload: NeuroChannelRuleCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroChannelRuleRead:
    rule = ChannelRulesService().create_rule(
        session,
        workspace_id=auth.workspace_id,
        actor_user_id=auth.user_id,
        payload=payload.model_dump(),
    )
    session.commit()
    session.refresh(rule)
    return NeuroChannelRuleRead.model_validate(rule)


@router.delete("/channel-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel_rule(
    rule_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> None:
    try:
        ChannelRulesService().delete_rule(
            session, workspace_id=auth.workspace_id, rule_id=str(rule_id)
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc


@router.post("/targets/{target_id}/pause", response_model=NeuroTargetRead)
def post_target_pause(
    target_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroTargetRead:
    return _target_status("pause", str(target_id), session, auth)


@router.post("/targets/{target_id}/blacklist", response_model=NeuroChannelRuleRead)
def post_target_blacklist(
    target_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroChannelRuleRead:
    return _target_rule("blacklist", str(target_id), session, auth)


@router.post("/targets/{target_id}/whitelist", response_model=NeuroChannelRuleRead)
def post_target_whitelist(
    target_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroChannelRuleRead:
    return _target_rule("whitelist", str(target_id), session, auth)


@router.post("/targets/{target_id}/resume", response_model=NeuroTargetRead)
def post_target_resume(
    target_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroTargetRead:
    return _target_status("resume", str(target_id), session, auth)


@router.post("/campaigns/{campaign_id}/start", response_model=NeuroCampaignRead)
def post_campaign_start(
    campaign_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroCampaignRead:
    return _campaign_lifecycle("start", str(campaign_id), session, auth)


@router.post("/campaigns/{campaign_id}/pause", response_model=NeuroCampaignRead)
def post_campaign_pause(
    campaign_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroCampaignRead:
    return _campaign_lifecycle("pause", str(campaign_id), session, auth)


@router.post("/campaigns/{campaign_id}/stop", response_model=NeuroCampaignRead)
def post_campaign_stop(
    campaign_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroCampaignRead:
    return _campaign_lifecycle("stop", str(campaign_id), session, auth)


@router.get("/generated-comments", response_model=NeuroGeneratedCommentPageRead)
def get_generated_comments(
    campaign_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
    _valid_query: None = Depends(_reject_unknown_generated_query_params),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroGeneratedCommentPageRead:
    try:
        if campaign_id is not None:
            repository.require_campaign(
                session, campaign_id=str(campaign_id), workspace_id=auth.workspace_id
            )
    except ValueError as exc:
        raise _neuro_error(exc) from exc
    items, total = repository.list_generated_comments(
        session,
        workspace_id=auth.workspace_id,
        campaign_id=str(campaign_id) if campaign_id is not None else None,
        page=page,
        limit=limit,
    )
    return NeuroGeneratedCommentPageRead(
        items=[NeuroGeneratedCommentRead.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/generated-comments/{comment_id}", response_model=NeuroGeneratedCommentRead)
def get_generated_comment(
    comment_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroGeneratedCommentRead:
    try:
        comment = repository.require_generated_comment(
            session, comment_id=str(comment_id), workspace_id=auth.workspace_id
        )
        return NeuroGeneratedCommentRead.model_validate(comment)
    except ValueError as exc:
        raise _neuro_error(exc) from exc


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
    if not enqueue_neuro_observe_campaign(
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
    if not enqueue_neuro_observe_target(
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
    if not enqueue_neuro_refresh_target_metadata(campaign.id, str(target_id), auth.workspace_id):
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
    job_id = neuro_generate_comment_job_id(observed.id, force=request.force)
    if not enqueue_neuro_generate_comment(
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


@router.get("/attempts", response_model=NeuroAttemptPageRead)
def get_attempts(
    campaign_id: UUID | None = Query(default=None),
    generated_comment_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
    _valid_query: None = Depends(_reject_unknown_attempt_query_params),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroAttemptPageRead:
    try:
        if campaign_id is not None:
            repository.require_campaign(
                session, campaign_id=str(campaign_id), workspace_id=auth.workspace_id
            )
    except ValueError as exc:
        raise _neuro_error(exc) from exc
    items, total = repository.list_attempts(
        session,
        workspace_id=auth.workspace_id,
        campaign_id=str(campaign_id) if campaign_id is not None else None,
        generated_comment_id=str(generated_comment_id)
        if generated_comment_id is not None
        else None,
        page=page,
        limit=limit,
    )
    return NeuroAttemptPageRead(
        items=[NeuroAttemptRead.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/attempts/{attempt_id}", response_model=NeuroAttemptRead)
def get_attempt(
    attempt_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroAttemptRead:
    try:
        attempt = repository.require_attempt_for_workspace(
            session, attempt_id=str(attempt_id), workspace_id=auth.workspace_id
        )
        return NeuroAttemptRead.model_validate(attempt)
    except NeuroCommentingError as exc:
        raise _neuro_domain_error(exc) from exc


@router.patch("/generated-comments/{comment_id}", response_model=NeuroGeneratedCommentRead)
def patch_generated_comment(
    comment_id: UUID,
    payload: NeuroGeneratedCommentUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroGeneratedCommentRead:
    try:
        comment = ApprovalService().edit_comment(
            session,
            comment_id=str(comment_id),
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
            edited_text=payload.edited_text,
        )
        session.commit()
        session.refresh(comment)
        return NeuroGeneratedCommentRead.model_validate(comment)
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc


@router.post("/generated-comments/{comment_id}/approve", response_model=NeuroGeneratedCommentRead)
def post_generated_comment_approve(
    comment_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroGeneratedCommentRead:
    try:
        comment, _attempt = ApprovalService().approve_comment(
            session,
            comment_id=str(comment_id),
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
        )
        session.commit()
        session.refresh(comment)
        return NeuroGeneratedCommentRead.model_validate(comment)
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc


@router.post("/generated-comments/{comment_id}/reject", response_model=NeuroGeneratedCommentRead)
def post_generated_comment_reject(
    comment_id: UUID,
    payload: NeuroGeneratedCommentRejectRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroGeneratedCommentRead:
    try:
        comment = ApprovalService().reject_comment(
            session,
            comment_id=str(comment_id),
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
            reason=payload.reason,
        )
        session.commit()
        session.refresh(comment)
        return NeuroGeneratedCommentRead.model_validate(comment)
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc


@router.post("/generated-comments/{comment_id}/send", response_model=NeuroManualSendRead)
def post_generated_comment_send(
    comment_id: UUID,
    payload: NeuroManualSendRequest | None = None,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> NeuroManualSendRead:
    request = payload or NeuroManualSendRequest()
    attempt = None
    try:
        comment = repository.require_generated_comment(
            session, comment_id=str(comment_id), workspace_id=auth.workspace_id
        )
        attempt = repository.get_attempt_for_generated_comment(
            session, generated_comment_id=comment.id
        )
        if attempt is None:
            attempt = repository.create_attempt_for_generated_comment(session, comment=comment)
        service = SenderService()
        AnalyticsService().write_event(
            session,
            workspace_id=auth.workspace_id,
            campaign_id=attempt.campaign_id,
            account_id=attempt.account_id,
            target_id=attempt.target_id,
            observed_post_id=attempt.observed_post_id,
            generated_comment_id=attempt.generated_comment_id,
            attempt_id=attempt.id,
            event_type="manual_send_requested",
            message="manual neuro-comment send requested",
            data={"attempt_id": attempt.id},
        )
        service.preflight_attempt(
            session,
            attempt_id=attempt.id,
            workspace_id=auth.workspace_id,
        )
        if attempt.status == NeuroAttemptStatus.SENT.value and attempt.telegram_message_id:
            session.commit()
            session.refresh(attempt)
            return NeuroManualSendRead(
                accepted=False,
                attempt=NeuroAttemptRead.model_validate(attempt),
                job_id=None,
                queue_name=None,
                send_enabled=True,
                disabled_reason=None,
            )
        if request.enqueue:
            if (
                not settings.neuro_comment_tdlib_send_enabled
                or settings.neuro_comment_require_redis_limiter_for_send
            ):
                service.send_attempt(
                    session,
                    attempt_id=attempt.id,
                    workspace_id=auth.workspace_id,
                )
            if not enqueue_neuro_send_attempt(attempt.id, auth.workspace_id):
                AnalyticsService().write_event(
                    session,
                    workspace_id=auth.workspace_id,
                    campaign_id=attempt.campaign_id,
                    account_id=attempt.account_id,
                    target_id=attempt.target_id,
                    observed_post_id=attempt.observed_post_id,
                    generated_comment_id=attempt.generated_comment_id,
                    attempt_id=attempt.id,
                    event_type="manual_send_blocked",
                    event_level=NeuroEventLevel.ERROR,
                    message="manual neuro-comment send enqueue failed",
                    data={"error_code": "QUEUE_UNAVAILABLE"},
                )
                session.commit()
                _raise_queue_unavailable()
            AnalyticsService().write_event(
                session,
                workspace_id=auth.workspace_id,
                campaign_id=attempt.campaign_id,
                account_id=attempt.account_id,
                target_id=attempt.target_id,
                observed_post_id=attempt.observed_post_id,
                generated_comment_id=attempt.generated_comment_id,
                attempt_id=attempt.id,
                event_type="manual_send_enqueued",
                message="manual neuro-comment send enqueued",
                data={"attempt_id": attempt.id},
            )
            session.commit()
            session.refresh(attempt)
            return NeuroManualSendRead(
                accepted=True,
                attempt=NeuroAttemptRead.model_validate(attempt),
                job_id=f"neuro-send-{attempt.id}",
                queue_name=NEURO_COMMENT_QUEUE_NAME,
                send_enabled=True,
                disabled_reason=None,
            )
        else:
            if not _sync_send_allowed():
                AnalyticsService().write_event(
                    session,
                    workspace_id=auth.workspace_id,
                    campaign_id=attempt.campaign_id,
                    account_id=attempt.account_id,
                    target_id=attempt.target_id,
                    observed_post_id=attempt.observed_post_id,
                    generated_comment_id=attempt.generated_comment_id,
                    attempt_id=attempt.id,
                    event_type="manual_send_blocked",
                    event_level=NeuroEventLevel.WARNING,
                    message="synchronous live neuro-comment send is disabled",
                    data={"error_code": "NEURO_COMMENT_SYNC_SEND_DISABLED"},
                )
                raise NeuroConflictError(
                    "Synchronous neuro-comment sending is disabled outside local/test.",
                    error_code="NEURO_COMMENT_SYNC_SEND_DISABLED",
                )
            service.send_attempt(
                session,
                attempt_id=attempt.id,
                workspace_id=auth.workspace_id,
            )
        session.commit()
        session.refresh(attempt)
        return NeuroManualSendRead(
            accepted=False,
            attempt=NeuroAttemptRead.model_validate(attempt),
            job_id=None,
            queue_name=None,
            send_enabled=True,
            disabled_reason=None,
        )
    except NeuroCommentingError as exc:
        if attempt is not None:
            AnalyticsService().write_event(
                session,
                workspace_id=auth.workspace_id,
                campaign_id=attempt.campaign_id,
                account_id=attempt.account_id,
                target_id=attempt.target_id,
                observed_post_id=attempt.observed_post_id,
                generated_comment_id=attempt.generated_comment_id,
                attempt_id=attempt.id,
                event_type="manual_send_blocked",
                event_level=NeuroEventLevel.WARNING,
                message="manual neuro-comment send blocked",
                data={"error_code": exc.error_code},
            )
        session.commit()
        raise _neuro_domain_error(exc) from exc
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc


@router.get("/events", response_model=NeuroEventPageRead)
def get_events(
    campaign_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
    _valid_query: None = Depends(_reject_unknown_event_query_params),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> NeuroEventPageRead:
    try:
        if campaign_id is not None:
            repository.require_campaign(
                session, campaign_id=str(campaign_id), workspace_id=auth.workspace_id
            )
    except ValueError as exc:
        raise _neuro_error(exc) from exc
    items, total = repository.list_events(
        session,
        workspace_id=auth.workspace_id,
        campaign_id=str(campaign_id) if campaign_id is not None else None,
        page=page,
        limit=limit,
    )
    return NeuroEventPageRead(
        items=[NeuroEventRead.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
    )


def _campaign_lifecycle(
    action: str,
    campaign_id: str,
    session: Session,
    auth: AuthContext,
) -> NeuroCampaignRead:
    service = CampaignService()
    try:
        if action == "start":
            campaign = service.start_campaign(
                session,
                campaign_id=campaign_id,
                workspace_id=auth.workspace_id,
                actor_user_id=auth.user_id,
            )
        elif action == "pause":
            campaign = service.pause_campaign(
                session,
                campaign_id=campaign_id,
                workspace_id=auth.workspace_id,
                actor_user_id=auth.user_id,
            )
        else:
            campaign = service.stop_campaign(
                session,
                campaign_id=campaign_id,
                workspace_id=auth.workspace_id,
                actor_user_id=auth.user_id,
            )
        session.commit()
        session.refresh(campaign)
        return NeuroCampaignRead.model_validate(campaign)
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc


def _target_status(
    action: str,
    target_id: str,
    session: Session,
    auth: AuthContext,
) -> NeuroTargetRead:
    service = ChannelRulesService()
    try:
        if action == "pause":
            target = service.pause_target(
                session,
                target_id=target_id,
                workspace_id=auth.workspace_id,
                actor_user_id=auth.user_id,
            )
        else:
            target = service.resume_target(
                session,
                target_id=target_id,
                workspace_id=auth.workspace_id,
                actor_user_id=auth.user_id,
            )
        session.commit()
        session.refresh(target)
        return NeuroTargetRead.model_validate(target)
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc


def _target_rule(
    rule_type: str,
    target_id: str,
    session: Session,
    auth: AuthContext,
) -> NeuroChannelRuleRead:
    service = ChannelRulesService()
    try:
        target = service.require_target(
            session, workspace_id=auth.workspace_id, target_id=target_id
        )
        rule = service.create_rule(
            session,
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
            payload={"target_ref": target.channel_ref, "rule_type": rule_type},
        )
        session.commit()
        session.refresh(rule)
        return NeuroChannelRuleRead.model_validate(rule)
    except ValueError as exc:
        session.rollback()
        raise _neuro_error(exc) from exc


def _neuro_error(exc: ValueError) -> AppError:
    message = str(exc)
    not_found = {
        "account not found",
        "campaign not found",
        "campaign account not found",
        "channel rule not found",
        "generated comment not found",
        "limit not found",
        "observed post not found",
        "attempt not found",
        "target not found",
    }
    return AppError(
        status_code=status.HTTP_404_NOT_FOUND
        if message in not_found
        else status.HTTP_400_BAD_REQUEST,
        error_code=_error_code(message),
        error_class="not_found" if message in not_found else "validation",
        message=message,
    )


def _error_code(message: str) -> str:
    return message.upper().replace(" ", "_").replace("-", "_")


def _neuro_domain_error(exc: NeuroCommentingError) -> AppError:
    return AppError(
        status_code=int(exc.status_code),
        error_code=exc.error_code,
        error_class=exc.error_class,
        message=exc.message,
    )


def _raise_queue_unavailable() -> None:
    raise AppError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        error_code="QUEUE_UNAVAILABLE",
        error_class="queue",
        message="neuro-comment job queue is unavailable",
    )


def _sync_send_allowed() -> bool:
    return settings.app_env in {"local", "development", "test"}
