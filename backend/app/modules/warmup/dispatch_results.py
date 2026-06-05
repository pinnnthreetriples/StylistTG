from __future__ import annotations

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.adapters.warmup_tdlib import WarmupActionResult
from app.models import WarmupSession, WarmupStatus
from app.modules.account_lifecycle.interfaces import AccountLifecycleState, advance
from app.modules.account_survival import events as survival_events
from app.modules.warmup.channel_state import service as channel_state_service
from app.modules.warmup.events import write_warmup_event
from app.modules.warmup.isolation import release_claim
from app.modules.warmup.p2p import record_p2p_contact
from app.modules.warmup.pre_production import should_start_pre_production, start_pre_production

if TYPE_CHECKING:
    from .dispatch_context import _ActionContextResolution


def _isolation_owner(session_id: str) -> str:
    return f"warmup:{session_id}"


def _write_dispatch_skip(
    session: Session,
    warmup_session: WarmupSession,
    action_type: str,
    resolution: "_ActionContextResolution",
) -> None:
    write_warmup_event(
        session,
        warmup_session,
        "task_skipped",
        {
            "day": warmup_session.current_day,
            "action_type": action_type,
            "execution_mode": warmup_session.execution_mode,
            "reason": resolution.skip_reason,
            "metadata": dict(resolution.metadata),
        },
    )


def _write_write_action_disabled_skip(
    session: Session, warmup_session: WarmupSession, action_type: str
) -> None:
    write_warmup_event(
        session,
        warmup_session,
        "task_skipped",
        {
            "day": warmup_session.current_day,
            "action_type": action_type,
            "execution_mode": warmup_session.execution_mode,
            "reason": "write_action_not_enabled",
        },
    )


def _record_dispatch_action_failure(
    session: Session,
    warmup_session: WarmupSession,
    action_type: str,
    result: WarmupActionResult,
    *,
    action_context: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    failed_action = {
        "action_type": action_type,
        "status": result.status,
        "error_code": result.error_code,
        "error_class": result.error_class,
        "retry_after_seconds": result.retry_after_seconds,
        "metadata": dict(result.metadata),
    }
    write_warmup_event(
        session,
        warmup_session,
        "task_failed",
        {
            "day": warmup_session.current_day,
            "action_type": action_type,
            "execution_mode": warmup_session.execution_mode,
            "status": result.status,
            "error_code": result.error_code,
            "error_class": result.error_class,
            "retry_after_seconds": result.retry_after_seconds,
            "metadata": dict(result.metadata),
        },
    )
    if _action_result_label(result) == "flood_wait":
        survival_events.on_flood_wait(
            session,
            account_id=warmup_session.account_id,
            workspace_id=warmup_session.workspace_id,
            now=datetime.now(UTC),
            action_type=action_type,
        )
    survival_events.on_warmup_action_executed(
        action_type=action_type,
        result=_action_result_label(result),
        workspace_id=warmup_session.workspace_id,
    )
    _record_channel_action_result_if_needed(
        session,
        warmup_session,
        action_type=action_type,
        result=result,
        action_context=action_context or {},
        now=now or datetime.now(UTC),
    )
    return failed_action


def _record_dispatch_action_success(
    session: Session,
    warmup_session: WarmupSession,
    *,
    action_type: str,
    result: WarmupActionResult,
    action_context: dict[str, Any],
    is_live: bool,
    now: datetime,
) -> None:
    _record_p2p_contact_if_needed(
        session,
        warmup_session,
        action_type=action_type,
        action_context=action_context,
        is_live=is_live,
        now=now,
    )
    _record_channel_action_result_if_needed(
        session,
        warmup_session,
        action_type=action_type,
        result=result,
        action_context=action_context,
        now=now,
    )
    write_warmup_event(
        session,
        warmup_session,
        "session_action_executed" if is_live else "session_action_simulated",
        {
            "day": warmup_session.current_day,
            "action_type": action_type,
            "execution_mode": warmup_session.execution_mode,
            "simulated": not is_live,
            "metadata": dict(result.metadata),
        },
    )
    survival_events.on_warmup_action_executed(
        action_type=action_type,
        result="success",
        workspace_id=warmup_session.workspace_id,
    )


def _record_channel_action_result_if_needed(
    session: Session,
    warmup_session: WarmupSession,
    *,
    action_type: str,
    result: WarmupActionResult,
    action_context: dict[str, Any],
    now: datetime,
) -> None:
    channel_ref = action_context.get("channel_ref")
    if not channel_ref:
        return
    if action_type != "join_chat" and action_context.get("channel_subscribed") is not True:
        return
    channel_state_service.record_action_result(
        session,
        warmup_session,
        action_type,
        str(channel_ref),
        result,
        now=now,
    )


def _record_p2p_contact_if_needed(
    session: Session,
    warmup_session: WarmupSession,
    *,
    action_type: str,
    action_context: dict[str, Any],
    is_live: bool,
    now: datetime,
) -> None:
    if action_type != "p2p_send" or not is_live:
        return
    receiver_account_id = action_context.get("peer_account_id")
    if not receiver_account_id:
        return
    try:
        contact_summary = record_p2p_contact(
            session,
            workspace_id=warmup_session.workspace_id,
            sender_account_id=warmup_session.account_id,
            receiver_account_id=str(receiver_account_id),
            now=now,
        )
        write_warmup_event(
            session,
            warmup_session,
            "p2p_contact_recorded",
            {
                "day": warmup_session.current_day,
                "receiver_account_id": receiver_account_id,
                **contact_summary,
            },
        )
    except ValueError as exc:
        write_warmup_event(
            session,
            warmup_session,
            "p2p_contact_recording_failed",
            {
                "day": warmup_session.current_day,
                "receiver_account_id": receiver_account_id,
                "error": str(exc),
            },
        )


def _action_result_label(result: WarmupActionResult) -> str:
    status = str(result.status or "").strip().lower()
    error_code = str(result.error_code or "").strip().lower()
    if status == "flood_wait" or "flood_wait" in error_code:
        return "flood_wait"
    return status or "failed"


def _warmup_preset(warmup_session: WarmupSession) -> str:
    snapshot = warmup_session.strategy_snapshot_json or {}
    if isinstance(snapshot, dict) and snapshot.get("preset_kind"):
        return str(snapshot["preset_kind"])
    strategy = warmup_session.strategy
    if strategy is not None and strategy.preset_kind:
        return str(strategy.preset_kind)
    return "unknown"


def _complete_dispatch_session(
    session: Session, warmup_session: WarmupSession, *, now: datetime
) -> None:
    warmup_session.status = WarmupStatus.COMPLETED
    warmup_session.completed_at = now
    warmup_session.next_step_at = None
    warmup_session.next_micro_session_at = None
    warmup_session.updated_at = now
    write_warmup_event(
        session,
        warmup_session,
        "completed",
        {"day": warmup_session.current_day, "execution_mode": warmup_session.execution_mode},
    )
    _advance_account_to_pre_production(session, warmup_session, now)
    if should_start_pre_production(warmup_session):
        start_pre_production(
            session,
            account_id=warmup_session.account_id,
            workspace_id=warmup_session.workspace_id,
            source_warmup_session_id=warmup_session.id,
            source_warmup_session=warmup_session,
            now=now,
        )
    survival_events.on_warmup_completed(
        session,
        account_id=warmup_session.account_id,
        workspace_id=warmup_session.workspace_id,
        now=now,
        preset=_warmup_preset(warmup_session),
    )
    if release_claim(
        session,
        account_id=warmup_session.account_id,
        held_by=_isolation_owner(warmup_session.id),
    ):
        write_warmup_event(
            session,
            warmup_session,
            "isolation_released",
            {"reason": "session_completed"},
        )


def _advance_account_to_pre_production(
    session: Session,
    warmup_session: WarmupSession,
    now: datetime,
) -> None:
    account = warmup_session.account
    if account.lifecycle_state == AccountLifecycleState.IMPORTED.value:
        advance(
            session,
            account,
            to_state=AccountLifecycleState.COLD_SOAK,
            now=now,
            reason="legacy_completion_catchup",
            metadata={"warmup_session_id": warmup_session.id},
        )
    if account.lifecycle_state == AccountLifecycleState.COLD_SOAK.value:
        advance(
            session,
            account,
            to_state=AccountLifecycleState.WARMING,
            now=now,
            reason="legacy_completion_catchup",
            metadata={"warmup_session_id": warmup_session.id},
        )
    advance(
        session,
        account,
        to_state=AccountLifecycleState.PRE_PRODUCTION,
        now=now,
        reason="warmup_session_completed",
        metadata={"warmup_session_id": warmup_session.id},
    )
