"""Warmup API router.

Compatibility owner for app.api.warmup.
Do not add behavior to the legacy app.api wrapper.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.db import SessionLocal, get_session
from app.errors import AppError
from app.modules.warmup import service as warmup_service
from app.modules.warmup.contracts import (
    WarmupActionMetadataRead,
    WarmupActionPresetRequest,
    WarmupBootstrapChannelCreate,
    WarmupBootstrapChannelPatch,
    WarmupBootstrapChannelRead,
    WarmupCyclicCreateRead,
    WarmupCyclicCreateRequest,
    WarmupDisabledActionsRequest,
    WarmupEventPageRead,
    WarmupEventSeverityRead,
    WarmupLiveEventPageRead,
    WarmupIsolationStatusRead,
    WarmupPauseRequest,
    WarmupReadinessRead,
    WarmupSelectableAccountRead,
    WarmupSessionCreateRequest,
    WarmupSessionPageRead,
    WarmupSessionRead,
    WarmupSessionStatusRead,
    WarmupStrategyRead,
    WarmupValidateRead,
    WarmupValidateRequest,
)
from app.modules.warmup.bootstrap_pool import service as bootstrap_service
from app.modules.warmup.selectable_accounts import list_selectable_accounts
from app.modules.warmup.errors import WarmupError
from app.modules.warmup.cyclic import setup_cyclic_warmups
from app.modules.auth.dependencies import (
    AuthContext,
    require_authenticated,
    require_mutation_permission,
    require_role,
)
from app.modules.auth.service import resolve_auth_context


router = APIRouter()
warmup_router = APIRouter(prefix="/api/warmup", tags=["warmup"])
actions_router = APIRouter(prefix="/api/warmup-actions", tags=["warmup-actions"])
session_alias_router = APIRouter(prefix="/api/warmup-sessions", tags=["warmup"])
selectable_accounts_router = APIRouter(prefix="/api/warmup-selectable-accounts", tags=["warmup"])
events_router = APIRouter(prefix="/api/warmup-events", tags=["warmup"])
bootstrap_router = APIRouter(
    prefix="/api/warmup-bootstrap-channels", tags=["warmup-bootstrap-channels"]
)
settings = warmup_service.settings


@selectable_accounts_router.get("", response_model=list[WarmupSelectableAccountRead])
def get_warmup_selectable_accounts(
    workspace_id: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=128),
    country: str | None = Query(default=None, max_length=8),
    role: str | None = Query(default=None, max_length=32),
    proxy_ok_only: bool = Query(default=False),
    hide_in_work: bool = Query(default=False),
    limit: int = Query(default=500, ge=1, le=500),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> list[WarmupSelectableAccountRead]:
    if workspace_id is not None and workspace_id != auth.workspace_id:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="WORKSPACE_FORBIDDEN",
            error_class="authorization",
            message="workspace_id does not match authenticated workspace",
        )
    return list_selectable_accounts(
        session,
        workspace_id=auth.workspace_id,
        search=search,
        country=country,
        role=role,
        proxy_ok_only=proxy_ok_only,
        hide_in_work=hide_in_work,
        limit=limit,
    )


@events_router.get("", response_model=WarmupLiveEventPageRead)
def get_warmup_events(
    workspace_id: str | None = Query(default=None),
    account_id: str | None = Query(default=None),
    severity: list[WarmupEventSeverityRead] | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> WarmupLiveEventPageRead:
    _ensure_requested_workspace(workspace_id, auth)
    return warmup_service.list_warmup_event_feed_page(
        session,
        workspace_id=auth.workspace_id,
        account_id=account_id,
        severities=[item.value for item in severity] if severity else None,
        cursor=cursor,
        limit=limit,
    )


@events_router.get("/stream")
def stream_warmup_events(
    request: Request,
    workspace_id: str | None = Query(default=None),
    account_id: str | None = Query(default=None),
    severity: list[WarmupEventSeverityRead] | None = Query(default=None),
    cursor: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    auth = _resolve_stream_auth(request, session)
    _ensure_requested_workspace(workspace_id, auth)
    return StreamingResponse(
        _warmup_event_stream(
            request,
            workspace_id=auth.workspace_id,
            account_id=account_id,
            severities=[item.value for item in severity] if severity else None,
            cursor=cursor,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@actions_router.get("/metadata", response_model=list[WarmupActionMetadataRead])
def get_warmup_action_metadata(
    auth: AuthContext = Depends(require_authenticated),
) -> list[WarmupActionMetadataRead]:
    _ = auth
    return warmup_service.list_action_metadata()


@bootstrap_router.get("", response_model=list[WarmupBootstrapChannelRead])
def get_warmup_bootstrap_channels(
    category: str | None = Query(default=None),
    language: str | None = Query(default=None),
    session: Session = Depends(get_session),
    _auth: AuthContext = Depends(require_role("admin")),
) -> list[WarmupBootstrapChannelRead]:
    return [
        WarmupBootstrapChannelRead.model_validate(row)
        for row in bootstrap_service.list_bootstrap_channels(
            session, category=category, language=language
        )
    ]


@bootstrap_router.post(
    "",
    response_model=WarmupBootstrapChannelRead,
    status_code=status.HTTP_201_CREATED,
)
def post_warmup_bootstrap_channel(
    payload: WarmupBootstrapChannelCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_role("admin")),
) -> WarmupBootstrapChannelRead:
    try:
        row = bootstrap_service.create_bootstrap_channel(
            session,
            channel_ref=payload.channel_ref,
            category=payload.category,
            language=payload.language,
            country=payload.country,
            added_by=auth.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return WarmupBootstrapChannelRead.model_validate(row)


@bootstrap_router.patch("/{channel_id}", response_model=WarmupBootstrapChannelRead)
def patch_warmup_bootstrap_channel(
    channel_id: UUID,
    payload: WarmupBootstrapChannelPatch,
    session: Session = Depends(get_session),
    _auth: AuthContext = Depends(require_role("admin")),
) -> WarmupBootstrapChannelRead:
    try:
        row = bootstrap_service.patch_bootstrap_channel(
            session,
            str(channel_id),
            category=payload.category,
            language=payload.language,
            country=payload.country,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="channel not found")
    return WarmupBootstrapChannelRead.model_validate(row)


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


@session_alias_router.post(
    "/cyclic", response_model=WarmupCyclicCreateRead, status_code=status.HTTP_201_CREATED
)
def post_warmup_cyclic_sessions(
    payload: WarmupCyclicCreateRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> WarmupCyclicCreateRead:
    try:
        rows = setup_cyclic_warmups(
            session,
            account_ids=[str(account_id) for account_id in payload.account_ids],
            workspace_id=auth.workspace_id,
            start_hour=payload.start_hour,
            end_hour=payload.end_hour,
            days_total=payload.days_total,
            strategy_preset=payload.strategy_preset.value,
        )
        session.commit()
        return WarmupCyclicCreateRead(items=[warmup_service.session_read(row) for row in rows])
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


def _warmup_error(exc: WarmupError) -> AppError:
    return AppError(
        status_code=exc.status_code or status.HTTP_400_BAD_REQUEST,
        error_code=exc.error_code,
        error_class=exc.error_class,
        message=exc.legacy_message,
        field_errors=list(exc.field_errors),
    )


def _ensure_requested_workspace(workspace_id: str | None, auth: AuthContext) -> None:
    if workspace_id is not None and workspace_id != auth.workspace_id:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="WORKSPACE_FORBIDDEN",
            error_class="authorization",
            message="workspace_id does not match authenticated workspace",
        )


class _StreamAuthRequest:
    def __init__(self, headers: dict[str, str]) -> None:
        self._headers = headers

    @property
    def headers(self) -> dict[str, str]:
        return self._headers


def _resolve_stream_auth(request: Request, session: Session) -> AuthContext:
    if request.headers.get("Authorization"):
        return resolve_auth_context(request, session)
    access_token = request.query_params.get("access_token")
    if not access_token:
        return resolve_auth_context(request, session)
    headers = dict(request.headers)
    headers["Authorization"] = f"Bearer {access_token}"
    return resolve_auth_context(_StreamAuthRequest(headers), session)


async def _warmup_event_stream(
    request: Request,
    *,
    workspace_id: str,
    account_id: str | None,
    severities: list[str] | None,
    cursor: str | None,
):
    next_cursor = cursor
    while not await request.is_disconnected():
        with SessionLocal() as stream_session:
            page = warmup_service.list_warmup_event_feed_page(
                stream_session,
                workspace_id=workspace_id,
                account_id=account_id,
                severities=severities,
                cursor=next_cursor,
                limit=100,
                include_accounts=False,
            )
        if page.items:
            for item in page.items:
                next_cursor = item.id
                yield f"data: {item.model_dump_json()}\n\n"
        else:
            yield ": keepalive\n\n"
        await asyncio.sleep(2)


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
router.include_router(bootstrap_router)
router.include_router(selectable_accounts_router)
router.include_router(events_router)
