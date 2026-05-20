from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.contracts.quarantine import AccountQuarantineRead, ReleaseRequest
from app.db import get_session
from app.models import utc_now
from app.services.account_quarantine import QuarantineNotFound, get_active_quarantine, release_quarantine
from app.services.auth_context import AuthContext, require_authenticated, require_role
from app.services.sensitive_audit import record_sensitive_audit_event

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("/{account_id}/quarantine", response_model=AccountQuarantineRead | None)
def get_account_quarantine(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    row = get_active_quarantine(session, account_id=account_id, workspace_id=auth.workspace_id)
    return AccountQuarantineRead.model_validate(row) if row is not None else None


@router.post("/{account_id}/quarantine/release", response_model=AccountQuarantineRead)
def release_account_quarantine(
    account_id: str,
    payload: ReleaseRequest,
    request: Request,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_role("admin")),
):
    require_account_in_workspace(session, account_id, auth)
    before = get_active_quarantine(session, account_id=account_id, workspace_id=auth.workspace_id)
    if before is None:
        raise HTTPException(status_code=404, detail="active quarantine not found")

    before_snapshot = {
        "id": before.id,
        "reason": before.reason,
        "until": before.until.isoformat(),
        "metadata_json": dict(before.metadata_json or {}),
    }
    if payload.override_gate_block:
        metadata = dict(before.metadata_json or {})
        metadata["release_override_until"] = (utc_now() + timedelta(hours=24)).isoformat()
        metadata["release_override_reason"] = payload.reason
        before.metadata_json = metadata
        session.flush()

    try:
        after = release_quarantine(
            session,
            quarantine_id=before.id,
            workspace_id=auth.workspace_id,
            released_by=auth.user_id,
            reason=payload.reason,
        )
    except QuarantineNotFound as exc:
        raise HTTPException(status_code=404, detail="active quarantine not found") from exc

    record_sensitive_audit_event(
        session,
        workspace_id=auth.workspace_id,
        actor_user_id=auth.user_id,
        action="account_quarantine.released",
        entity_type="account_quarantine",
        entity_id=after.id,
        account_id=account_id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        reason=payload.reason,
        metadata={
            "before": before_snapshot,
            "after": {
                "released_at": after.released_at.isoformat() if after.released_at else None,
                "released_by_user_id": after.released_by_user_id,
                "metadata_json": dict(after.metadata_json or {}),
            },
            "override_gate_block": payload.override_gate_block,
        },
    )
    session.commit()
    return AccountQuarantineRead.model_validate(after)
