from __future__ import annotations

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.adapters.warmup_tdlib import WarmupActionResult
from app.models import WarmupSession, WarmupStatus
from app.modules.warmup.events import write_warmup_event
from app.modules.warmup.isolation import release_claim
from app.modules.warmup.p2p import record_p2p_contact

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
