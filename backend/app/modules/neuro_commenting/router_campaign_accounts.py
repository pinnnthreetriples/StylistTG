from __future__ import annotations

from uuid import UUID
from fastapi import Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import (
    NeuroCampaignAccountCreate,
    NeuroCampaignAccountPageRead,
    NeuroCampaignAccountRead,
)
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated
from app.modules.auth.dependencies import require_mutation_permission
from app.modules.neuro_commenting import repository
from app.modules.neuro_commenting.campaign_account_service import CampaignAccountService

from .router_base import router
from .router_common import (
    _neuro_error,
    _reject_unknown_list_query_params,
)


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
