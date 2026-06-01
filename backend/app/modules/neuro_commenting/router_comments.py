from __future__ import annotations

from uuid import UUID
from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.contracts.queues import NEURO_COMMENT_QUEUE_NAME
from app.config import settings
from app.schemas import (
    NeuroAttemptRead,
    NeuroGeneratedCommentPageRead,
    NeuroGeneratedCommentRead,
    NeuroGeneratedCommentRejectRequest,
    NeuroGeneratedCommentUpdate,
    NeuroManualSendRead,
    NeuroManualSendRequest,
)
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated
from app.modules.auth.dependencies import require_mutation_permission
from app.modules.neuro_commenting import repository
from app.modules.neuro_commenting.analytics_service import AnalyticsService
from app.modules.neuro_commenting.approval_service import ApprovalService
from app.modules.neuro_commenting.enums import NeuroAttemptStatus
from app.modules.neuro_commenting.enums import NeuroEventLevel
from app.modules.neuro_commenting.errors import NeuroCommentingError
from app.modules.neuro_commenting.errors import NeuroConflictError
from app.modules.neuro_commenting.sender_service import SenderService

from .router_base import router
from .router_common import (
    _neuro_domain_error,
    _neuro_error,
    _raise_queue_unavailable,
    _reject_unknown_generated_query_params,
    _runtime_api,
    _sync_send_allowed,
)


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
            if not _runtime_api().enqueue_neuro_send_attempt(attempt.id, auth.workspace_id):
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
