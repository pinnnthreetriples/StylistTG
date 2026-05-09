from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.errors import AppError
from app.job_queue.rq import enqueue_warmup_dispatch_tick, enqueue_warmup_due_sessions
from app.models import (
    ACTIVE_WARMUP_STATUSES,
    Account,
    WarmupExecutionMode,
    WarmupSession,
    WarmupStatus,
    WarmupStrategy,
)
from app.schemas import (
    WarmupEventPageRead,
    WarmupEventRead,
    WarmupIsolationClaimRead,
    WarmupIsolationStatusRead,
    WarmupPauseRequest,
    WarmupReadinessRead,
    WarmupSessionCreateRequest,
    WarmupSessionPageRead,
    WarmupSessionRead,
    WarmupSessionStatusRead,
    WarmupSessionSummaryRead,
    WarmupStrategyRead,
    WarmupValidateRead,
    WarmupValidateRequest,
)
from app.services.auth_context import AuthContext, require_authenticated, require_mutation_permission
from app.services.warmup import (
    create_warmup_session,
    delete_warmup_session,
    get_warmup_session,
    list_warmup_events,
    list_warmup_sessions,
    pause_warmup_session,
    resume_warmup_session,
    write_warmup_event,
)
from app.services.warmup_isolation import get_claim, release_claim
from app.services.warmup_readiness import validate_warmup_readiness

router = APIRouter(prefix="/api/warmup", tags=["warmup"])


@router.get("/readiness", response_model=WarmupReadinessRead)
def get_warmup_readiness(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> WarmupReadinessRead:
    active_sessions = session.scalar(
        select(func.count())
        .select_from(WarmupSession)
        .where(
            WarmupSession.workspace_id == auth.workspace_id,
            WarmupSession.status.in_([s.value for s in ACTIVE_WARMUP_STATUSES]),
        )
    )
    strategies_available = session.scalar(
        select(func.count())
        .select_from(WarmupStrategy)
        .where(
            (WarmupStrategy.workspace_id == auth.workspace_id)
            | (WarmupStrategy.workspace_id.is_(None))
        )
    )
    return WarmupReadinessRead(
        workers_enabled=settings.warmup_workers_enabled,
        dry_run=settings.warmup_dry_run,
        redis_connected=_redis_connected(),
        database_connected=True,
        active_sessions=int(active_sessions or 0),
        strategies_available=int(strategies_available or 0),
    )


@router.post("/validate", response_model=WarmupValidateRead)
def post_warmup_validate(
    payload: WarmupValidateRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> WarmupValidateRead:
    return validate_warmup_readiness(
        session,
        account_id=payload.account_id,
        strategy_id=payload.strategy_id,
        workspace_id=auth.workspace_id,
    )


@router.get("/strategies", response_model=list[WarmupStrategyRead])
def get_warmup_strategies(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> list[WarmupStrategyRead]:
    strategies = session.execute(
        select(WarmupStrategy)
        .where((WarmupStrategy.workspace_id == auth.workspace_id) | (WarmupStrategy.workspace_id.is_(None)))
        .order_by(WarmupStrategy.is_preset.desc(), WarmupStrategy.name.asc())
    ).scalars()
    return [
        WarmupStrategyRead(
            id=strategy.id,
            name=strategy.name,
            description=strategy.description,
            is_preset=strategy.is_preset,
            preset_kind=strategy.preset_kind,
            execution_mode=strategy.execution_mode,
            duration_days=strategy.duration_days,
            daily_action_limits=strategy.daily_action_limits_json or {},
            session_window_config=strategy.session_window_config_json or {},
            ui_summary=strategy.ui_summary_json or {},
        )
        for strategy in strategies
    ]


@router.post("/sessions", response_model=WarmupSessionRead, status_code=status.HTTP_201_CREATED)
def post_warmup_session(
    payload: WarmupSessionCreateRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> WarmupSessionRead:
    try:
        warmup_session = create_warmup_session(
            session,
            account_id=payload.account_id,
            strategy_id=payload.strategy_id,
            workspace_id=auth.workspace_id,
        )
        session.commit()
        session.refresh(warmup_session)
        enqueue_ok = True
        if settings.warmup_workers_enabled:
            enqueue_ok = (
                enqueue_warmup_due_sessions()
                if warmup_session.execution_mode == WarmupExecutionMode.DRY_RUN.value
                else enqueue_warmup_dispatch_tick()
            )
        if enqueue_ok is False:
            warmup_session.status = WarmupStatus.FAILED
            write_warmup_event(session, warmup_session, "queue_enqueue_failed", {})
            release_claim(
                session,
                account_id=warmup_session.account_id,
                held_by=f"warmup:{warmup_session.id}",
            )
            session.commit()
            raise AppError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                error_code="WARMUP_QUEUE_UNAVAILABLE",
                error_class="queue",
                message="warmup queue is unavailable",
            )
        return _session_read(warmup_session)
    except ValueError as exc:
        session.rollback()
        raise AppError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="WARMUP_SESSION_REJECTED",
            error_class="validation",
            message=str(exc),
        ) from exc


@router.get("/sessions", response_model=WarmupSessionPageRead)
def get_warmup_sessions(
    status_filter: list[str] | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> WarmupSessionPageRead:
    items, total = list_warmup_sessions(
        session,
        workspace_id=auth.workspace_id,
        statuses=status_filter,
        page=page,
        limit=limit,
    )
    return WarmupSessionPageRead(
        items=[_session_summary(item) for item in items],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/sessions/{session_id}", response_model=WarmupSessionRead)
def get_warmup_session_detail(
    session_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> WarmupSessionRead:
    try:
        return _session_read(get_warmup_session(session, session_id=session_id, workspace_id=auth.workspace_id))
    except ValueError as exc:
        raise _not_found(exc) from exc


@router.get("/sessions/{session_id}/status", response_model=WarmupSessionStatusRead)
def get_warmup_session_status(
    session_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> WarmupSessionStatusRead:
    try:
        warmup_session = get_warmup_session(session, session_id=session_id, workspace_id=auth.workspace_id)
    except ValueError as exc:
        raise _not_found(exc) from exc
    return WarmupSessionStatusRead(
        status=warmup_session.status,
        current_day=warmup_session.current_day,
        next_step_at=warmup_session.next_step_at,
        next_attempt_at=warmup_session.next_attempt_at,
    )


@router.put("/sessions/{session_id}/pause", response_model=WarmupSessionRead)
def put_warmup_session_pause(
    session_id: str,
    payload: WarmupPauseRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> WarmupSessionRead:
    try:
        warmup_session = pause_warmup_session(
            session,
            session_id=session_id,
            workspace_id=auth.workspace_id,
            reason=payload.reason,
        )
        session.commit()
        session.refresh(warmup_session)
        return _session_read(warmup_session)
    except ValueError as exc:
        session.rollback()
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            error_code="WARMUP_PAUSE_REJECTED",
            error_class="state_conflict",
            message=str(exc),
        ) from exc


@router.put("/sessions/{session_id}/resume", response_model=WarmupSessionRead)
def put_warmup_session_resume(
    session_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> WarmupSessionRead:
    try:
        warmup_session = resume_warmup_session(
            session,
            session_id=session_id,
            workspace_id=auth.workspace_id,
        )
        session.commit()
        session.refresh(warmup_session)
        return _session_read(warmup_session)
    except ValueError as exc:
        session.rollback()
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            error_code="WARMUP_RESUME_REJECTED",
            error_class="state_conflict",
            message=str(exc),
        ) from exc


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_warmup_session_endpoint(
    session_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> None:
    try:
        delete_warmup_session(session, session_id=session_id, workspace_id=auth.workspace_id)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise _not_found(exc) from exc


@router.get("/sessions/{session_id}/events", response_model=WarmupEventPageRead)
def get_warmup_session_events(
    session_id: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> WarmupEventPageRead:
    try:
        items, total = list_warmup_events(
            session,
            session_id=session_id,
            workspace_id=auth.workspace_id,
            page=page,
            limit=limit,
        )
    except ValueError as exc:
        raise _not_found(exc) from exc
    return WarmupEventPageRead(
        items=[
            WarmupEventRead(
                id=item.id,
                event_type=item.event_type,
                payload=item.payload_json,
                created_at=item.created_at,
            )
            for item in items
        ],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/isolation/by-account/{account_id}",
    response_model=WarmupIsolationStatusRead,
)
def get_warmup_isolation_status(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> WarmupIsolationStatusRead:
    """Phase 1: surface isolation claim so cross-module pages can warn users
    before mutating an account that warmup currently owns.

    The endpoint verifies the account belongs to the caller's workspace.
    Returns is_isolated=False with claim=null when no claim exists.
    """
    account = session.get(Account, account_id)
    if account is None or account.workspace_id != auth.workspace_id:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message="account not found",
        )
    claim = get_claim(session, account_id=account_id)
    if claim is None:
        return WarmupIsolationStatusRead(is_isolated=False, claim=None)
    return WarmupIsolationStatusRead(
        is_isolated=True,
        claim=WarmupIsolationClaimRead(
            account_id=claim.account_id,
            workspace_id=claim.workspace_id,
            held_by=claim.held_by,
            reason=claim.reason,
            acquired_at=claim.acquired_at,
        ),
    )


def _redis_connected() -> bool:
    try:
        client = Redis.from_url(settings.redis_url, socket_connect_timeout=0.2)
        try:
            return bool(client.ping())
        finally:
            client.close()
    except Exception:
        return False


def _session_read(warmup_session: WarmupSession) -> WarmupSessionRead:
    return WarmupSessionRead(
        id=warmup_session.id,
        account_id=warmup_session.account_id,
        strategy_id=warmup_session.strategy_id,
        strategy_name=warmup_session.strategy.name,
        status=warmup_session.status,
        execution_mode=warmup_session.execution_mode,
        duration_days=warmup_session.duration_days,
        current_day=warmup_session.current_day,
        cadence_hours=warmup_session.cadence_hours,
        timezone=warmup_session.timezone,
        next_step_at=warmup_session.next_step_at,
        last_step_at=warmup_session.last_step_at,
        next_attempt_at=warmup_session.next_attempt_at,
        next_micro_session_at=warmup_session.next_micro_session_at,
        last_micro_session_at=warmup_session.last_micro_session_at,
        consecutive_failures=warmup_session.consecutive_failures,
        daily_counters=warmup_session.daily_counters_json or {},
        trusted_peer_ids=warmup_session.trusted_peer_ids_json or [],
        proxy_snapshot=warmup_session.proxy_snapshot_json,
        created_at=warmup_session.created_at,
        updated_at=warmup_session.updated_at,
        started_at=warmup_session.started_at,
        paused_at=warmup_session.paused_at,
        completed_at=warmup_session.completed_at,
        worker_id=warmup_session.worker_id,
    )


def _session_summary(warmup_session: WarmupSession) -> WarmupSessionSummaryRead:
    return WarmupSessionSummaryRead(
        id=warmup_session.id,
        account_id=warmup_session.account_id,
        account_label=warmup_session.account.external_ref,
        strategy_name=warmup_session.strategy.name,
        status=warmup_session.status,
        execution_mode=warmup_session.execution_mode,
        duration_days=warmup_session.duration_days,
        current_day=warmup_session.current_day,
        cadence_hours=warmup_session.cadence_hours,
        next_step_at=warmup_session.next_step_at,
        next_micro_session_at=warmup_session.next_micro_session_at,
        updated_at=warmup_session.updated_at,
    )


def _not_found(exc: ValueError) -> AppError:
    return AppError(
        status_code=status.HTTP_404_NOT_FOUND,
        error_code="WARMUP_SESSION_NOT_FOUND",
        error_class="not_found",
        message=str(exc),
    )
