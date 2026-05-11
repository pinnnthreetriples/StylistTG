from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccountExportRequest
from app.services.sensitive_audit import record_sensitive_audit_event


@dataclass(frozen=True)
class ReaperReport:
    mode: str
    expired_export_requests: int
    deleted_objects: int
    destructive_actions_enabled: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "expired_export_requests": self.expired_export_requests,
            "deleted_objects": self.deleted_objects,
            "destructive_actions_enabled": self.destructive_actions_enabled,
        }


def run_reaper_report(
    session: Session, *, workspace_id: str | None = None, mode: str = "dry_run"
) -> ReaperReport:
    now = datetime.now(UTC)
    statement = (
        select(AccountExportRequest)
        .where(AccountExportRequest.expires_at.is_not(None))
        .where(AccountExportRequest.expires_at < now)
    )
    if workspace_id is not None:
        statement = statement.where(AccountExportRequest.workspace_id == workspace_id)
    expired = session.execute(statement).scalars().all()
    deleted_objects = 0
    if mode == "execute_safe":
        for request in expired:
            request.status = "expired"
            record_sensitive_audit_event(
                session,
                workspace_id=request.workspace_id,
                actor_type="system",
                action="account.export.expired",
                entity_type="account_export_request",
                entity_id=request.id,
                account_id=request.account_id,
                metadata={"mode": mode},
            )
        session.commit()
    return ReaperReport(
        mode=mode,
        expired_export_requests=len(expired),
        deleted_objects=deleted_objects,
        destructive_actions_enabled=False,
    )
