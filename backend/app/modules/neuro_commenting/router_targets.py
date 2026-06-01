from __future__ import annotations

from uuid import UUID
from fastapi import Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import (
    NeuroChannelRuleRead,
    NeuroTargetBulkCreateRead,
    NeuroTargetBulkCreateRequest,
    NeuroTargetBulkSkippedItemRead,
    NeuroTargetCreate,
    NeuroTargetPageRead,
    NeuroTargetRead,
)
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated
from app.modules.auth.dependencies import require_mutation_permission
from app.modules.neuro_commenting import repository
from app.modules.neuro_commenting.target_service import TargetService

from .router_base import router
from .router_common import (
    _neuro_error,
    _reject_unknown_list_query_params,
    _target_rule,
    _target_status,
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
