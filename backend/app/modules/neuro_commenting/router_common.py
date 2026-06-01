from __future__ import annotations

# pyright: reportUnusedFunction=false

import sys

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import AppError
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated, require_mutation_permission
from app.modules.neuro_commenting.campaign_service import CampaignService
from app.modules.neuro_commenting.channel_rules_service import ChannelRulesService
from app.modules.neuro_commenting.errors import NeuroCommentingError
from app.schemas import NeuroCampaignRead, NeuroChannelRuleRead, NeuroTargetRead

_LIST_QUERY_PARAMS = {"page", "limit"}
_GENERATED_QUERY_PARAMS = {"campaign_id", "page", "limit"}
_OBSERVED_QUERY_PARAMS = {"campaign_id", "target_id", "page", "limit"}
_ATTEMPT_QUERY_PARAMS = {"campaign_id", "generated_comment_id", "page", "limit"}
_EVENT_QUERY_PARAMS = {"campaign_id", "page", "limit"}

__all__ = ["AuthContext", "require_authenticated", "require_mutation_permission"]


def _runtime_api():
    return sys.modules["app.modules.neuro_commenting.router"]


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
