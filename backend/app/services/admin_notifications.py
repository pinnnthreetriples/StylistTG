from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.contracts.notifications import (
    NotificationDeliveryResult,
    NotificationPayload,
)
from app.models import (
    Account,
    AccountQuarantine,
    AccountStatusObservation,
    AdminNotificationLog,
    NeuroCommentEvent,
    Workspace,
    new_id,
    utc_now,
)

QUARANTINE_EPIDEMIC_THRESHOLD = 0.1
GATE_BLOCK_BURST_THRESHOLD = 0.3
PROXY_OUTAGE_THRESHOLD = 0.8


class NotificationChannel(Protocol):
    def send(
        self,
        session: Session,
        payload: NotificationPayload,
    ) -> NotificationDeliveryResult | None: ...


def collect_triggers(session: Session, *, now: datetime) -> list[NotificationPayload]:
    """Scan all workspaces and return notification candidates for this tick."""
    payloads: list[NotificationPayload] = []
    workspace_ids = session.execute(select(Workspace.id)).scalars().all()
    for workspace_id in workspace_ids:
        payloads.extend(_quarantine_epidemic(session, workspace_id=workspace_id, now=now))
        payloads.extend(_ggr_drop(session, workspace_id=workspace_id, now=now))
        payloads.extend(_gate_block_burst(session, workspace_id=workspace_id, now=now))
        payloads.extend(_proxy_outage(session, workspace_id=workspace_id, now=now))
    return payloads


def is_recently_notified(
    session: Session,
    *,
    workspace_id: str,
    trigger_code: str,
    dedup_window: timedelta = timedelta(hours=1),
) -> bool:
    row = session.execute(
        select(AdminNotificationLog.id)
        .where(AdminNotificationLog.workspace_id == workspace_id)
        .where(AdminNotificationLog.trigger_code == trigger_code)
        .where(AdminNotificationLog.triggered_at >= utc_now() - dedup_window)
        .limit(1)
    ).first()
    return row is not None


def deliver(
    session: Session,
    payload: NotificationPayload,
    *,
    channels: Sequence[NotificationChannel],
) -> list[NotificationDeliveryResult]:
    results: list[NotificationDeliveryResult] = []
    for channel in channels:
        result = channel.send(session, payload)
        if result is not None:
            results.append(result)

    session.add(
        AdminNotificationLog(
            id=new_id(),
            workspace_id=str(payload.workspace_id),
            trigger_code=payload.trigger_code,
            triggered_at=payload.triggered_at,
            metadata_json=payload.metadata,
            delivered_channels=[result.channel for result in results if result.success],
        )
    )
    session.flush()
    return results


def _quarantine_epidemic(
    session: Session,
    *,
    workspace_id: str,
    now: datetime,
) -> list[NotificationPayload]:
    account_count = _count(
        session, select(func.count(Account.id)).where(Account.workspace_id == workspace_id)
    )
    if account_count == 0:
        return []
    quarantined_count = _count(
        session,
        select(func.count(AccountQuarantine.id))
        .where(AccountQuarantine.workspace_id == workspace_id)
        .where(AccountQuarantine.released_at.is_(None))
        .where(AccountQuarantine.until > now)
        .where(AccountQuarantine.started_at >= now - timedelta(hours=1)),
    )
    ratio = quarantined_count / account_count
    if ratio <= QUARANTINE_EPIDEMIC_THRESHOLD:
        return []
    return [
        NotificationPayload(
            workspace_id=UUID(workspace_id),
            trigger_code="quarantine_epidemic",
            severity="warning",
            title="Quarantine spike detected",
            body_text="More than 10% of workspace accounts entered quarantine in the last hour.",
            metadata={
                "account_count": account_count,
                "quarantined_accounts": quarantined_count,
                "quarantine_ratio": round(ratio, 4),
                "window_minutes": 60,
            },
            triggered_at=now,
        )
    ]


def _ggr_drop(
    session: Session,
    *,
    workspace_id: str,
    now: datetime,
) -> list[NotificationPayload]:
    # Disabled until GGR history persistence lands; re-enable here once
    # the workspace-level ggr_history table is populated.
    return []


def _gate_block_burst(
    session: Session,
    *,
    workspace_id: str,
    now: datetime,
) -> list[NotificationPayload]:
    since = now - timedelta(minutes=30)
    total_sends = _count(
        session,
        select(func.count(NeuroCommentEvent.id))
        .where(NeuroCommentEvent.workspace_id == workspace_id)
        .where(NeuroCommentEvent.created_at >= since)
        .where(NeuroCommentEvent.event_type.like("comment_send%")),
    )
    if total_sends == 0:
        return []
    blocked = _count(
        session,
        select(func.count(NeuroCommentEvent.id))
        .where(NeuroCommentEvent.workspace_id == workspace_id)
        .where(NeuroCommentEvent.created_at >= since)
        .where(NeuroCommentEvent.event_type == "comment_send_blocked_by_gate"),
    )
    ratio = blocked / total_sends
    if ratio <= GATE_BLOCK_BURST_THRESHOLD:
        return []
    return [
        NotificationPayload(
            workspace_id=UUID(workspace_id),
            trigger_code="gate_block_burst",
            severity="warning",
            title="Safety gate block burst detected",
            body_text="More than 30% of recent comment send attempts were blocked by safety gate.",
            metadata={
                "blocked_sends": blocked,
                "total_sends": total_sends,
                "blocked_ratio": round(ratio, 4),
                "window_minutes": 30,
            },
            triggered_at=now,
        )
    ]


def _proxy_outage(
    session: Session,
    *,
    workspace_id: str,
    now: datetime,
) -> list[NotificationPayload]:
    since = now - timedelta(minutes=15)
    total = _count(
        session,
        select(func.count(AccountStatusObservation.id))
        .where(AccountStatusObservation.workspace_id == workspace_id)
        .where(AccountStatusObservation.observed_at >= since),
    )
    if total == 0:
        return []
    unhealthy = _count(
        session,
        select(func.count(AccountStatusObservation.id))
        .where(AccountStatusObservation.workspace_id == workspace_id)
        .where(AccountStatusObservation.observed_at >= since)
        .where(AccountStatusObservation.proxy_healthy.is_(False)),
    )
    ratio = unhealthy / total
    if ratio <= PROXY_OUTAGE_THRESHOLD:
        return []
    return [
        NotificationPayload(
            workspace_id=UUID(workspace_id),
            trigger_code="proxy_outage",
            severity="critical",
            title="Workspace proxy outage detected",
            body_text="Most recent account status observations report unhealthy proxies.",
            metadata={
                "unhealthy_observations": unhealthy,
                "total_observations": total,
                "unhealthy_ratio": round(ratio, 4),
                "window_minutes": 15,
            },
            triggered_at=now,
        )
    ]


def _count(session: Session, statement: Select[tuple[int]]) -> int:
    value = session.scalar(statement)
    return int(value or 0)
