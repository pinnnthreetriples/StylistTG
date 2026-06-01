from __future__ import annotations

# pyright: reportPrivateUsage=false

from uuid import UUID
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import NeuroCampaignRead
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_mutation_permission

from .router_base import router
from .router_common import _campaign_lifecycle


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
