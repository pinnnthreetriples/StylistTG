from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.warmup_tdlib_contracts import WRITE_ACTION_TYPES
from app.config import Settings, settings
from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    Account,
    WarmupExecutionMode,
    WarmupPresetKind,
    WarmupSession,
    WarmupStatus,
    WarmupStrategy,
    new_id,
)
from app.modules.account_lifecycle.interfaces import (
    AccountLifecycleState,
    advance,
    detect_idle_accounts,
    list_idle_candidate_workspaces,
)
from app.modules.warmup import repository
from app.modules.warmup.events import write_warmup_event

IDLE_KEEPALIVE_STRATEGY_NAME = "IDLE_KEEPALIVE"
IDLE_KEEPALIVE_DURATION_DAYS = 30
IDLE_KEEPALIVE_CADENCE_HOURS = 12
IDLE_KEEPALIVE_ACTION_LIMITS = {"feed_read": 3, "view_dialogs": 2}


def create_idle_warmup_session(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    now: datetime | None = None,
) -> WarmupSession:
    existing = repository.active_warmup_for_account(
        session,
        account_id=account_id,
        workspace_id=workspace_id,
    )
    if existing is not None:
        return existing
    account = _account_or_raise(session, account_id=account_id, workspace_id=workspace_id)
    if account.lifecycle_state != AccountLifecycleState.IDLE.value:
        raise ValueError("account is not idle")
    timestamp = now or datetime.now(UTC)
    strategy = _get_or_create_idle_strategy(session, workspace_id=workspace_id)
    warmup_session = WarmupSession(
        id=new_id(),
        workspace_id=workspace_id,
        account_id=account_id,
        strategy_id=strategy.id,
        status=WarmupStatus.SCHEDULED,
        current_day=0,
        cadence_hours=IDLE_KEEPALIVE_CADENCE_HOURS,
        next_step_at=timestamp,
        execution_mode=WarmupExecutionMode.DRY_RUN.value,
        duration_days=IDLE_KEEPALIVE_DURATION_DAYS,
        daily_counters_json={},
        disabled_actions_json=sorted(WRITE_ACTION_TYPES),
        lifecycle_state="idle",
    )
    session.add(warmup_session)
    session.flush()
    write_warmup_event(
        session,
        warmup_session,
        "idle_warmup_session_created",
        {
            "strategy_name": IDLE_KEEPALIVE_STRATEGY_NAME,
            "read_only_actions": sorted(IDLE_KEEPALIVE_ACTION_LIMITS),
        },
    )
    return warmup_session


def run_idle_warmup_sweep(
    session: Session,
    *,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    now: datetime | None = None,
    config: Settings = settings,
) -> int:
    if not config.warmup_idle_detection_enabled:
        return 0
    timestamp = now or datetime.now(UTC)
    account_ids = detect_idle_accounts(
        session,
        workspace_id,
        threshold_minutes=config.warmup_idle_threshold_minutes,
        now=timestamp,
    )
    transitioned = 0
    for account_id in account_ids:
        account = _account_or_raise(session, account_id=account_id, workspace_id=workspace_id)
        advance(
            session,
            account,
            to_state=AccountLifecycleState.IDLE,
            now=timestamp,
            reason="idle_detection_threshold_elapsed",
            metadata={"threshold_minutes": config.warmup_idle_threshold_minutes},
        )
        create_idle_warmup_session(
            session,
            account_id=account.id,
            workspace_id=workspace_id,
            now=timestamp,
        )
        transitioned += 1
    session.flush()
    return transitioned


def run_idle_warmup_sweep_all_workspaces(
    session: Session,
    *,
    now: datetime | None = None,
    config: Settings = settings,
) -> int:
    if not config.warmup_idle_detection_enabled:
        return 0
    timestamp = now or datetime.now(UTC)
    return sum(
        run_idle_warmup_sweep(
            session,
            workspace_id=workspace_id,
            now=timestamp,
            config=config,
        )
        for workspace_id in list_idle_candidate_workspaces(session)
    )


def resume_account_from_idle(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    now: datetime | None = None,
    reason: str = "combat_job_created",
) -> WarmupSession | None:
    account = _account_or_raise(session, account_id=account_id, workspace_id=workspace_id)
    if account.lifecycle_state != AccountLifecycleState.IDLE.value:
        return None
    timestamp = now or datetime.now(UTC)
    warmup_session = repository.active_warmup_for_account(
        session,
        account_id=account_id,
        workspace_id=workspace_id,
    )
    if warmup_session is not None and warmup_session.lifecycle_state == "idle":
        warmup_session.status = WarmupStatus.COMPLETED
        warmup_session.completed_at = timestamp
        warmup_session.next_step_at = None
        warmup_session.next_micro_session_at = None
        warmup_session.updated_at = timestamp
        write_warmup_event(
            session,
            warmup_session,
            "idle_session_stopped",
            {"reason": reason},
        )
    advance(
        session,
        account,
        to_state=AccountLifecycleState.ACTIVE,
        now=timestamp,
        reason=reason,
    )
    session.flush()
    return warmup_session


def _get_or_create_idle_strategy(session: Session, *, workspace_id: str) -> WarmupStrategy:
    existing = (
        session.execute(
            select(WarmupStrategy)
            .where(WarmupStrategy.workspace_id == workspace_id)
            .where(WarmupStrategy.name == IDLE_KEEPALIVE_STRATEGY_NAME)
            .limit(1)
        )
        .scalars()
        .first()
    )
    if existing is not None:
        return existing
    strategy = WarmupStrategy(
        id=new_id(),
        workspace_id=workspace_id,
        name=IDLE_KEEPALIVE_STRATEGY_NAME,
        description="Read-only idle keepalive warmup for accounts outside combat work.",
        tier_limits_json={"cadence_hours": IDLE_KEEPALIVE_CADENCE_HOURS, "profile_required": False},
        target_channels_json=[],
        is_preset=True,
        execution_mode=WarmupExecutionMode.DRY_RUN.value,
        preset_kind=WarmupPresetKind.CUSTOM.value,
        duration_days=IDLE_KEEPALIVE_DURATION_DAYS,
        daily_action_limits_json={
            str(day): dict(IDLE_KEEPALIVE_ACTION_LIMITS)
            for day in range(1, IDLE_KEEPALIVE_DURATION_DAYS + 1)
        },
        session_window_config_json={
            "micro_sessions_per_day": {"min": 1, "max": 2},
            "minutes_per_session": {"min": 5, "max": 15},
        },
        ui_summary_json={
            "audience_hint": "Idle account keepalive",
            "risk_level": "low",
            "read_only": True,
        },
    )
    session.add(strategy)
    session.flush()
    return strategy


def _account_or_raise(session: Session, *, account_id: str, workspace_id: str) -> Account:
    account = (
        session.execute(
            select(Account)
            .where(Account.id == account_id)
            .where(Account.workspace_id == workspace_id)
            .limit(1)
        )
        .scalars()
        .first()
    )
    if account is None:
        raise ValueError("account not found")
    return account


__all__ = [
    "IDLE_KEEPALIVE_STRATEGY_NAME",
    "create_idle_warmup_session",
    "resume_account_from_idle",
    "run_idle_warmup_sweep",
    "run_idle_warmup_sweep_all_workspaces",
]
