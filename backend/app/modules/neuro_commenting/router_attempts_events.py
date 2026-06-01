from __future__ import annotations

from uuid import UUID
from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import (
    NeuroAttemptPageRead,
    NeuroAttemptRead,
    NeuroEventPageRead,
    NeuroEventRead,
)
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated
from app.modules.neuro_commenting import repository
from app.modules.neuro_commenting.errors import NeuroCommentingError

from .router_base import router
from .router_common import (
    _neuro_domain_error,
    _neuro_error,
    _reject_unknown_attempt_query_params,
    _reject_unknown_event_query_params,
)


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
