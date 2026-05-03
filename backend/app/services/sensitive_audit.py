from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SensitiveAuditEvent, new_id, utc_now
from app.services.secret_redaction import redact_metadata, redact_text


def record_sensitive_audit_event(
    session: Session,
    *,
    workspace_id: str,
    action: str,
    entity_type: str,
    actor_user_id: str | None = None,
    actor_type: str = "user",
    entity_id: str | None = None,
    account_id: str | None = None,
    request_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    reason: str | None = None,
    override_reason: str | None = None,
    risk_level: str | None = None,
    risk_score: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> SensitiveAuditEvent:
    event = SensitiveAuditEvent(
        id=new_id(),
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        actor_type=actor_type,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        account_id=account_id,
        request_id=request_id,
        ip_hash=_hash_optional(ip),
        user_agent_hash=_hash_optional(user_agent),
        reason=redact_text(reason) if reason else None,
        override_reason=redact_text(override_reason) if override_reason else None,
        risk_level=risk_level,
        risk_score=risk_score,
        metadata_json=redact_metadata(metadata or {}),
        created_at=utc_now(),
    )
    session.add(event)
    return event


def list_sensitive_audit_events(
    session: Session,
    *,
    workspace_id: str,
    account_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[SensitiveAuditEvent], int]:
    statement = select(SensitiveAuditEvent).where(SensitiveAuditEvent.workspace_id == workspace_id)
    if account_id is not None:
        statement = statement.where(SensitiveAuditEvent.account_id == account_id)
    rows = (
        session.execute(statement.order_by(SensitiveAuditEvent.created_at.desc()).offset(offset).limit(limit))
        .scalars()
        .all()
    )
    total = len(session.execute(statement).scalars().all())
    return rows, total


def audit_event_to_dict(event: SensitiveAuditEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "workspace_id": event.workspace_id,
        "actor_user_id": event.actor_user_id,
        "actor_type": event.actor_type,
        "action": event.action,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "account_id": event.account_id,
        "request_id": event.request_id,
        "reason": event.reason,
        "override_reason": event.override_reason,
        "risk_level": event.risk_level,
        "risk_score": event.risk_score,
        "metadata": event.metadata_json,
        "created_at": event.created_at,
    }


def _hash_optional(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
