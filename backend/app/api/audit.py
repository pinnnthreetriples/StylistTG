from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import SensitiveAuditEventPageRead, SensitiveAuditEventRead
from app.services.auth_context import AuthContext, require_authenticated
from app.services.sensitive_audit import audit_event_to_dict, list_sensitive_audit_events

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/events", response_model=SensitiveAuditEventPageRead)
def get_audit_events(
    account_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    rows, total = list_sensitive_audit_events(
        session,
        workspace_id=auth.workspace_id,
        account_id=account_id,
        limit=limit,
        offset=offset,
    )
    return SensitiveAuditEventPageRead(
        items=[SensitiveAuditEventRead(**audit_event_to_dict(row)) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
