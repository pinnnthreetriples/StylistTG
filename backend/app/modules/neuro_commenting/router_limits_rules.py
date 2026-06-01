from __future__ import annotations

# pyright: reportPrivateUsage=false

from uuid import UUID
from fastapi import Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import (
    NeuroChannelRuleCreate,
    NeuroChannelRulePageRead,
    NeuroChannelRuleRead,
    NeuroLimitCreate,
    NeuroLimitPageRead,
    NeuroLimitRead,
    NeuroLimitUpdate,
    NeuroPromptPresetListRead,
    NeuroPromptPresetRead,
)
from app.modules.neuro_commenting.channel_rules_service import ChannelRulesService
from app.modules.neuro_commenting.limits_service import LimitsService
from app.modules.neuro_commenting.prompt_presets import list_prompt_presets

from .router_base import router
from .router_common import (
    AuthContext,
    _neuro_error,
    _reject_unknown_list_query_params,
    require_authenticated,
    require_mutation_permission,
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
