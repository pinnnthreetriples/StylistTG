from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, new_id, utc_now
from app.services.secret_redaction import redact_metadata


def log_audit_event(
    session: Session,
    *,
    workspace_id: str,
    actor_user_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> AuditLog:
    row = AuditLog(
        id=new_id(),
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=redact_metadata(metadata or {}),
        request_id=request_id,
        created_at=utc_now(),
    )
    session.add(row)
    return row
