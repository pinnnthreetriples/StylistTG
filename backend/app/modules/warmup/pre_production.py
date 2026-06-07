from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Account, WarmupPreProductionSession, WarmupSession, new_id, utc_now
from app.modules.account_lifecycle.interfaces import AccountLifecycleState, advance
from app.modules.account_safety.interfaces import evaluate as evaluate_safety_gate
from app.modules.account_shared.interfaces import lookup_account
from app.modules.warmup.events import write_warmup_event


RUNNING_STATUS = "running"
COMPLETED_STATUS = "completed"
FAILED_STATUS = "failed"


class PreProductionRejectedError(ValueError):
    pass


def start_pre_production(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    duration_hours: int | None = None,
    source_warmup_session_id: str | None = None,
    source_warmup_session: WarmupSession | None = None,
    target_channels: Sequence[object] | None = None,
    config: Any = settings,
    now: datetime | None = None,
) -> WarmupPreProductionSession:
    if not bool(getattr(config, "warmup_pre_production_enabled", False)):
        raise PreProductionRejectedError("pre-production is disabled")

    timestamp = now or utc_now()
    account = lookup_account(session, account_id, workspace_id=workspace_id)
    if account is None:
        raise ValueError("account not found")
    _ensure_empty_profile(account)
    _ensure_safety_gate(session, account)
    _ensure_pre_production_state(session, account, timestamp, source_warmup_session_id)

    existing = _active_pre_production_session(
        session, account_id=account.id, workspace_id=account.workspace_id
    )
    if existing is not None:
        return existing

    resolved_duration_hours = _duration_hours(config, duration_hours)
    channels = _normalize_target_channels(
        target_channels
        if target_channels is not None
        else _target_channels_from_warmup(source_warmup_session)
    )
    task_plan = {
        "mode": "dry_run",
        "empty_profile_required": True,
        "neuro_comment": _run_pre_production_neuro_comment(account.id, channels),
        "mass_react": _run_pre_production_mass_react(account.id, channels),
    }
    row = WarmupPreProductionSession(
        id=new_id(),
        workspace_id=account.workspace_id,
        account_id=account.id,
        source_warmup_session_id=source_warmup_session_id,
        status=RUNNING_STATUS,
        duration_hours=resolved_duration_hours,
        started_at=timestamp,
        ends_at=timestamp + timedelta(hours=resolved_duration_hours),
        task_plan_json=task_plan,
        task_result_json={},
        created_at=timestamp,
        updated_at=timestamp,
    )
    session.add(row)
    session.flush()
    if source_warmup_session is not None:
        write_warmup_event(
            session,
            source_warmup_session,
            "pre_production_started",
            {
                "pre_production_session_id": row.id,
                "duration_hours": resolved_duration_hours,
                "target_channel_count": len(channels),
            },
        )
    return row


def complete_pre_production_session(
    session: Session,
    *,
    pre_production_session_id: str,
    workspace_id: str,
    success: bool,
    failure_code: str | None = None,
    failure_message: str | None = None,
    now: datetime | None = None,
) -> WarmupPreProductionSession:
    timestamp = now or utc_now()
    row = session.execute(
        select(WarmupPreProductionSession)
        .where(WarmupPreProductionSession.id == pre_production_session_id)
        .where(WarmupPreProductionSession.workspace_id == workspace_id)
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("pre-production session not found")
    if row.status != RUNNING_STATUS:
        return row

    account = lookup_account(session, row.account_id, workspace_id=workspace_id)
    if account is None:
        raise ValueError("account not found")

    row.completed_at = timestamp
    row.updated_at = timestamp
    if success:
        row.status = COMPLETED_STATUS
        row.task_result_json = {"status": "completed", "completed_at": timestamp.isoformat()}
        advance(
            session,
            account,
            to_state=AccountLifecycleState.ACTIVE,
            now=timestamp,
            reason="pre_production_completed",
            metadata={"pre_production_session_id": row.id},
        )
    else:
        row.status = FAILED_STATUS
        row.failure_code = failure_code or "pre_production_failed"
        row.failure_message = failure_message
        row.task_result_json = {
            "status": "failed",
            "failure_code": row.failure_code,
            "failed_at": timestamp.isoformat(),
        }
        advance(
            session,
            account,
            to_state=AccountLifecycleState.COLD_SOAK,
            now=timestamp,
            reason="pre_production_flood_wait"
            if _is_flood_wait(row.failure_code)
            else "pre_production_failed",
            metadata={"pre_production_session_id": row.id, "failure_code": row.failure_code},
        )
    session.flush()
    return row


def complete_due_pre_production_sessions(
    session: Session,
    *,
    workspace_id: str | None = None,
    now: datetime | None = None,
) -> int:
    timestamp = now or utc_now()
    query = select(WarmupPreProductionSession).where(
        WarmupPreProductionSession.status == RUNNING_STATUS,
        WarmupPreProductionSession.ends_at <= timestamp,
    )
    if workspace_id is not None:
        query = query.where(WarmupPreProductionSession.workspace_id == workspace_id)
    rows = list(session.execute(query).scalars())
    for row in rows:
        complete_pre_production_session(
            session,
            pre_production_session_id=row.id,
            workspace_id=row.workspace_id,
            success=True,
            now=timestamp,
        )
    return len(rows)


def get_pre_production_status(
    session: Session, *, account_id: str, workspace_id: str
) -> dict[str, Any]:
    account = lookup_account(session, account_id, workspace_id=workspace_id)
    if account is None:
        raise ValueError("account not found")
    row = session.execute(
        select(WarmupPreProductionSession)
        .where(WarmupPreProductionSession.workspace_id == workspace_id)
        .where(WarmupPreProductionSession.account_id == account_id)
        .order_by(
            WarmupPreProductionSession.created_at.desc(), WarmupPreProductionSession.id.desc()
        )
        .limit(1)
    ).scalar_one_or_none()
    return {
        "account_id": account.id,
        "lifecycle_state": account.lifecycle_state,
        "session_id": row.id if row is not None else None,
        "status": row.status if row is not None else None,
        "started_at": row.started_at if row is not None else None,
        "ends_at": row.ends_at if row is not None else None,
        "completed_at": row.completed_at if row is not None else None,
        "failure_code": row.failure_code if row is not None else None,
        "failure_message": row.failure_message if row is not None else None,
        "task_plan": row.task_plan_json if row is not None else {},
        "task_result": row.task_result_json if row is not None else {},
    }


def should_start_pre_production(warmup_session: WarmupSession, config: Any = settings) -> bool:
    if not bool(getattr(config, "warmup_pre_production_enabled", False)):
        return False
    for source in _strategy_flag_sources(warmup_session):
        if bool(source.get("enable_pre_production")):
            return True
    return False


def _run_pre_production_neuro_comment(
    account_id: str, target_channels: Sequence[str]
) -> dict[str, Any]:
    return {
        "source_module": "neuro_commenting",
        "mode": "dry_run",
        "action": "neuro_comment",
        "comment_count": _stable_count(account_id, minimum=3, maximum=5, salt="comments"),
        "target_channels": list(target_channels),
    }


def _run_pre_production_mass_react(
    account_id: str, target_channels: Sequence[str]
) -> dict[str, Any]:
    return {
        "source_module": "warmup.react_to_post",
        "mode": "dry_run",
        "action": "react_to_post",
        "reaction_count": _stable_count(account_id, minimum=5, maximum=10, salt="reactions"),
        "target_channels": list(target_channels),
    }


def _ensure_empty_profile(account: Account) -> None:
    profile = account.profile_state
    if profile is not None and profile.bio and profile.bio.strip():
        raise PreProductionRejectedError("profile bio must be empty")
    if profile is not None and profile.profile_photo_asset_id:
        raise PreProductionRejectedError("profile photo must be empty")
    if account.pinned_channel_ref:
        raise PreProductionRejectedError("profile links must be empty")


def _ensure_safety_gate(session: Session, account: Account) -> None:
    verdict = evaluate_safety_gate(
        session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="warmup",
    )
    if not verdict.eligible:
        reasons = ",".join(
            reason.code for reason in verdict.reasons if reason.severity == "blocked"
        )
        raise PreProductionRejectedError(f"safety gate blocked pre-production: {reasons}")


def _ensure_pre_production_state(
    session: Session,
    account: Account,
    timestamp: datetime,
    source_warmup_session_id: str | None,
) -> None:
    if account.lifecycle_state == AccountLifecycleState.PRE_PRODUCTION.value:
        return
    if account.lifecycle_state != AccountLifecycleState.WARMING.value:
        raise PreProductionRejectedError("account must be warming or pre_production")
    advance(
        session,
        account,
        to_state=AccountLifecycleState.PRE_PRODUCTION,
        now=timestamp,
        reason="pre_production_started",
        metadata={"warmup_session_id": source_warmup_session_id},
    )


def _active_pre_production_session(
    session: Session, *, account_id: str, workspace_id: str
) -> WarmupPreProductionSession | None:
    return session.execute(
        select(WarmupPreProductionSession)
        .where(WarmupPreProductionSession.workspace_id == workspace_id)
        .where(WarmupPreProductionSession.account_id == account_id)
        .where(WarmupPreProductionSession.status == RUNNING_STATUS)
        .order_by(WarmupPreProductionSession.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _duration_hours(config: Any, override: int | None) -> int:
    raw = (
        override
        if override is not None
        else getattr(config, "warmup_pre_production_duration_hours", 2)
    )
    try:
        value = int(raw)
    except TypeError, ValueError:
        value = 2
    return max(1, min(2, value))


def _target_channels_from_warmup(warmup_session: WarmupSession | None) -> Sequence[object]:
    if warmup_session is None:
        return ()
    snapshot = (
        warmup_session.strategy_snapshot_json
        if isinstance(warmup_session.strategy_snapshot_json, dict)
        else {}
    )
    channels = snapshot.get("target_channels_json") or snapshot.get("target_channels")
    if isinstance(channels, list):
        return cast(list[object], channels)
    strategy_channels = warmup_session.strategy.target_channels_json or []
    return cast(list[object], strategy_channels)


def _normalize_target_channels(raw_channels: Sequence[object]) -> list[str]:
    channels: list[str] = []
    for raw in raw_channels:
        value: object
        if isinstance(raw, dict):
            raw_channel = cast(Mapping[str, object], raw)
            value = (
                raw_channel.get("channel_ref")
                or raw_channel.get("ref")
                or raw_channel.get("id")
                or ""
            )
        else:
            value = raw
        text = str(value).strip()
        if text:
            channels.append(text)
    return channels[:10]


def _strategy_flag_sources(warmup_session: WarmupSession) -> list[dict[str, Any]]:
    snapshot = (
        warmup_session.strategy_snapshot_json
        if isinstance(warmup_session.strategy_snapshot_json, dict)
        else {}
    )
    sources: list[dict[str, Any]] = []
    for candidate in (
        snapshot,
        snapshot.get("tier_limits_json"),
        snapshot.get("ui_summary_json"),
        warmup_session.strategy.tier_limits_json,
        warmup_session.strategy.ui_summary_json,
    ):
        if isinstance(candidate, dict):
            sources.append(cast(dict[str, Any], candidate))
    return sources


def _stable_count(account_id: str, *, minimum: int, maximum: int, salt: str) -> int:
    span = maximum - minimum + 1
    digest = sha256(f"{account_id}:{salt}".encode("utf-8")).hexdigest()
    return minimum + (int(digest[:8], 16) % span)


def _is_flood_wait(error_code: str | None) -> bool:
    return "flood_wait" in (error_code or "").lower()


__all__ = [
    "PreProductionRejectedError",
    "complete_due_pre_production_sessions",
    "complete_pre_production_session",
    "get_pre_production_status",
    "should_start_pre_production",
    "start_pre_production",
]
