"""Warmup API router.

Compatibility owner for app.api.warmup.
Do not add behavior to the legacy app.api wrapper.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.db import get_session
from app.errors import AppError
from app.modules.account_lifecycle.contracts import (
    PreProductionStartRequest,
    PreProductionStatusRead,
)
from app.modules.warmup import service as warmup_service
from app.modules.warmup.contracts import (
    WarmupActionMetadataRead,
    WarmupActionPresetRequest,
    WarmupDisabledActionsRequest,
    WarmupEventPageRead,
    WarmupIsolationStatusRead,
    WarmupPauseRequest,
    WarmupReadinessRead,
    WarmupSessionCreateRequest,
    WarmupSessionPageRead,
    WarmupSessionRead,
    WarmupSessionStatusRead,
    WarmupStrategyRead,
    WarmupValidateRead,
    WarmupValidateRequest,
)
from app.modules.warmup.errors import WarmupError
from app.modules.warmup.interfaces import (
    get_pre_production_status,
    start_pre_production,
)
from app.modules.auth.dependencies import (
    AuthContext,
    require_authenticated,
    require_mutation_permission,
    require_role,
)


router = APIRouter()
warmup_router = APIRouter(prefix="/api/warmup", tags=["warmup"])
actions_router = APIRouter(prefix="/api/warmup-actions", tags=["warmup-actions"])
session_alias_router = APIRouter(prefix="/api/warmup-sessions", tags=["warmup"])
pre_production_router = APIRouter(prefix="/api/accounts", tags=["accounts"])
settings = warmup_service.settings


@actions_router.get("/metadata", response_model=list[WarmupActionMetadataRead])
def get_warmup_action_metadata(
    auth: AuthContext = Depends(require_authenticated),
) -> list[WarmupActionMetadataRead]:
    _ = auth
    return [
        WarmupActionMetadataRead(
            action_type=item.action_type,
            category=item.category,
            traffic_heavy=item.traffic_heavy,
            write_action=item.write_action,
            requires_premium=item.requires_premium,
        )
        for item in warmup_service.list_action_metadata()
    ]


@warmup_router.get("/readiness", response_model=WarmupReadinessRead)
def get_warmup_readiness(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> WarmupReadinessRead:
    return warmup_service.get_warmup_readiness(session, workspace_id=auth.workspace_id)


@warmup_router.post("/validate", response_model=WarmupValidateRead)
def post_warmup_validate(
    payload: WarmupValidateRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> WarmupValidateRead:
    return warmup_service.validate_warmup(
        session,
        account_id=payload.account_id,
        strategy_id=payload.strategy_id,
        workspace_id=auth.workspace_id,
    )


@warmup_router.get("/strategies", response_model=list[WarmupStrategyRead])
def get_warmup_strategies(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> list[WarmupStrategyRead]:
    return warmup_service.list_warmup_strategies(session, workspace_id=auth.workspace_id)


@warmup_router.post("/strategies/{strategy_id}/apply-preset", response_model=WarmupStrategyRead)
def post_warmup_strategy_apply_preset(
    strategy_id: UUID,
    payload: WarmupActionPresetRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_role("admin")),
) -> WarmupStrategyRead:
    try:
        return warmup_service.apply_action_preset_use_case(
            session,
            strategy_id=str(strategy_id),
            workspace_id=auth.workspace_id,
            preset=payload.preset,
            actor_user_id=auth.user_id,
        )
    except WarmupError as exc:
        session.rollback()
        raise _warmup_error(exc) from exc


@warmup_router.post(
    "/sessions", response_model=WarmupSessionRead, status_code=status.HTTP_201_CREATED
)
def post_warmup_session(
    payload: WarmupSessionCreateRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> WarmupSessionRead:
    try:
        return warmup_service.create_warmup_session_use_case(
            session,
            account_id=payload.account_id,
            strategy_id=payload.strategy_id,
            workspace_id=auth.workspace_id,
        )
    except WarmupError as exc:
        session.rollback()
        raise _warmup_error(exc) from exc


@warmup_router.get("/sessions", response_model=WarmupSessionPageRead)
def get_warmup_sessions(
    status_filter: list[str] | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1, le=10000),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> WarmupSessionPageRead:
    return warmup_service.list_warmup_sessions_page(
        session,
        workspace_id=auth.workspace_id,
        statuses=status_filter,
        page=page,
        limit=limit,
    )


@warmup_router.get("/sessions/{session_id}", response_model=WarmupSessionRead)
def get_warmup_session_detail(
    session_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> WarmupSessionRead:
    try:
        return warmup_service.get_warmup_session_detail(
            session, session_id=str(session_id), workspace_id=auth.workspace_id
        )
    except WarmupError as exc:
        raise _warmup_error(exc) from exc


@warmup_router.get("/sessions/{session_id}/status", response_model=WarmupSessionStatusRead)
def get_warmup_session_status(
    session_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> WarmupSessionStatusRead:
    try:
        return warmup_service.get_warmup_session_status(
            session, session_id=str(session_id), workspace_id=auth.workspace_id
        )
    except WarmupError as exc:
        raise _warmup_error(exc) from exc


@warmup_router.patch("/sessions/{session_id}/disabled-actions", response_model=WarmupSessionRead)
def patch_warmup_session_disabled_actions(
    session_id: UUID,
    payload: WarmupDisabledActionsRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> WarmupSessionRead:
    return _set_warmup_session_disabled_actions(session_id, payload, session, auth)


@session_alias_router.patch("/{session_id}/disabled-actions", response_model=WarmupSessionRead)
def patch_warmup_session_disabled_actions_alias(
    session_id: UUID,
    payload: WarmupDisabledActionsRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> WarmupSessionRead:
    return _set_warmup_session_disabled_actions(session_id, payload, session, auth)


@warmup_router.put("/sessions/{session_id}/pause", response_model=WarmupSessionRead)
def put_warmup_session_pause(
    session_id: UUID,
    payload: WarmupPauseRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> WarmupSessionRead:
    try:
        return warmup_service.pause_warmup_session_use_case(
            session,
            session_id=str(session_id),
            workspace_id=auth.workspace_id,
            reason=payload.reason,
        )
    except WarmupError as exc:
        session.rollback()
        raise _warmup_error(exc) from exc


@warmup_router.put("/sessions/{session_id}/resume", response_model=WarmupSessionRead)
def put_warmup_session_resume(
    session_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> WarmupSessionRead:
    try:
        return warmup_service.resume_warmup_session_use_case(
            session,
            session_id=str(session_id),
            workspace_id=auth.workspace_id,
        )
    except WarmupError as exc:
        session.rollback()
        raise _warmup_error(exc) from exc


@warmup_router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_warmup_session_endpoint(
    session_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> None:
    try:
        warmup_service.delete_warmup_session_use_case(
            session, session_id=str(session_id), workspace_id=auth.workspace_id
        )
    except WarmupError as exc:
        session.rollback()
        raise _warmup_error(exc) from exc


@warmup_router.get("/sessions/{session_id}/events", response_model=WarmupEventPageRead)
def get_warmup_session_events(
    session_id: UUID,
    page: int = Query(default=1, ge=1, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> WarmupEventPageRead:
    try:
        return warmup_service.list_warmup_session_events_page(
            session,
            session_id=str(session_id),
            workspace_id=auth.workspace_id,
            page=page,
            limit=limit,
        )
    except WarmupError as exc:
        raise _warmup_error(exc) from exc


@warmup_router.get(
    "/isolation/by-account/{account_id}",
    response_model=WarmupIsolationStatusRead,
)
def get_warmup_isolation_status(
    account_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> WarmupIsolationStatusRead:
    """Phase 1: surface isolation claim so cross-module pages can warn users
    before mutating an account that warmup currently owns.

    The endpoint verifies the account belongs to the caller's workspace.
    Returns is_isolated=False with claim=null when no claim exists.
    """
    account_id_str = str(account_id)
    require_account_in_workspace(session, account_id_str, auth)
    return warmup_service.get_warmup_isolation_status(session, account_id=account_id_str)


def _account_not_found_error(exc: ValueError | None = None) -> AppError:
    return AppError(
        status_code=status.HTTP_404_NOT_FOUND,
        error_code="ACCOUNT_NOT_FOUND",
        error_class="not_found",
        message=str(exc),
    )


@pre_production_router.post(
    "/{account_id}/pre-production/start", response_model=PreProductionStatusRead
)
def post_account_pre_production_start(
    account_id: str,
    payload: PreProductionStartRequest | None = None,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    try:
        start_pre_production(
            session,
            account_id=account_id,
            workspace_id=auth.workspace_id,
            duration_hours=payload.duration_hours if payload is not None else None,
        )
        session.commit()
        return PreProductionStatusRead(
            **get_pre_production_status(
                session, account_id=account_id, workspace_id=auth.workspace_id
            )
        )
    except WarmupError as exc:
        raise AppError(
            status_code=exc.status_code or status.HTTP_400_BAD_REQUEST,
            error_code=exc.error_code,
            error_class=exc.error_class,
            message=exc.legacy_message,
        ) from exc
    except ValueError as exc:
        message = str(exc)
        if message == "account not found":
            raise _account_not_found_error(exc) from exc
        raise AppError(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="PRE_PRODUCTION_REJECTED",
            error_class="warmup",
            message=message,
        ) from exc


@pre_production_router.get(
    "/{account_id}/pre-production/status", response_model=PreProductionStatusRead
)
def get_account_pre_production_status(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    try:
        return PreProductionStatusRead(
            **get_pre_production_status(
                session, account_id=account_id, workspace_id=auth.workspace_id
            )
        )
    except ValueError as exc:
        raise _account_not_found_error(exc) from exc


def _warmup_error(exc: WarmupError) -> AppError:
    return AppError(
        status_code=exc.status_code or status.HTTP_400_BAD_REQUEST,
        error_code=exc.error_code,
        error_class=exc.error_class,
        message=exc.legacy_message,
        field_errors=list(exc.field_errors),
    )


def _set_warmup_session_disabled_actions(
    session_id: UUID,
    payload: WarmupDisabledActionsRequest,
    session: Session,
    auth: AuthContext,
) -> WarmupSessionRead:
    try:
        return warmup_service.set_disabled_actions_use_case(
            session,
            session_id=str(session_id),
            workspace_id=auth.workspace_id,
            actions=payload.actions,
            actor_user_id=auth.user_id,
        )
    except WarmupError as exc:
        session.rollback()
        raise _warmup_error(exc) from exc


router.include_router(warmup_router)
router.include_router(actions_router)
router.include_router(session_alias_router)
router.include_router(pre_production_router)
