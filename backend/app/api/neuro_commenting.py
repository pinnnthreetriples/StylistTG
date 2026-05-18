from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.errors import AppError
from app.schemas import (
    NeuroCampaignAccountCreate,
    NeuroCampaignAccountPageRead,
    NeuroCampaignAccountRead,
    NeuroCampaignCreate,
    NeuroCampaignPageRead,
    NeuroCampaignRead,
    NeuroCampaignUpdate,
    NeuroEventPageRead,
    NeuroEventRead,
    NeuroGeneratedCommentPageRead,
    NeuroGeneratedCommentRead,
    NeuroGeneratedCommentRejectRequest,
    NeuroGeneratedCommentUpdate,
    NeuroTargetCreate,
    NeuroTargetPageRead,
    NeuroTargetRead,
)
from app.services.auth_context import (
    AuthContext,
    require_authenticated,
    require_mutation_permission,
)
from app.services.neuro_commenting import repository
from app.services.neuro_commenting.approval_service import ApprovalService
from app.services.neuro_commenting.campaign_account_service import CampaignAccountService
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.target_service import TargetService

router = APIRouter(prefix="/api/neuro-commenting", tags=["neuro-commenting"])
_LIST_QUERY_PARAMS = {"page", "limit"}
_GENERATED_QUERY_PARAMS = {"campaign_id", "page", "limit"}
_EVENT_QUERY_PARAMS = {"campaign_id", "page", "limit"}


def _reject_unknown_list_query_params(request: Request) -> None:
    _reject_unknown_query_params(request, allowed=_LIST_QUERY_PARAMS)


def _reject_unknown_generated_query_params(request: Request) -> None:
    _reject_unknown_query_params(request, allowed=_GENERATED_QUERY_PARAMS)


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


def _neuro_error(exc: ValueError) -> AppError:
    message = str(exc)
    not_found = {
        "account not found",
        "campaign not found",
        "campaign account not found",
        "generated comment not found",
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
