from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import AccountImportBatch, AccountImportItem, new_id, utc_now
from app.services.import_validation import validate_import_source
from app.services.sensitive_audit import record_sensitive_audit_event


def create_import_batch(
    session: Session,
    *,
    workspace_id: str,
    actor_user_id: str | None,
    source_type: str,
    label: str | None,
    dry_run: bool = True,
    metadata: dict[str, Any] | None = None,
) -> AccountImportBatch:
    row = AccountImportBatch(
        id=new_id(),
        workspace_id=workspace_id,
        created_by_user_id=actor_user_id,
        source_type=source_type,
        status="uploaded",
        label=label,
        dry_run=dry_run,
        object_key=f"imports/{workspace_id}/pending/{new_id()}/source",
        item_count=0,
        created_at=utc_now(),
    )
    session.add(row)
    record_sensitive_audit_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="account.import.uploaded",
        entity_type="account_import_batch",
        entity_id=row.id,
        metadata={"source_type": source_type, "dry_run": dry_run, "metadata": metadata or {}},
    )
    session.commit()
    session.refresh(row)
    return row


def validate_batch(
    session: Session,
    *,
    batch_id: str,
    workspace_id: str,
    content: bytes | None = None,
    metadata: dict[str, Any] | None = None,
) -> AccountImportBatch:
    batch = _require_batch(session, batch_id, workspace_id)
    batch.status = "validating"
    (
        session.query(AccountImportItem)
        .filter(
            AccountImportItem.batch_id == batch.id,
            AccountImportItem.workspace_id == batch.workspace_id,
        )
        .delete()
    )
    items = validate_import_source(
        source_type=batch.source_type, content=content, metadata=metadata
    )
    for item in items:
        payload = item.to_dict()
        session.add(
            AccountImportItem(
                id=new_id(),
                workspace_id=batch.workspace_id,
                batch_id=batch.id,
                source_ref_hash=payload["source_ref_hash"],
                status=payload["status"],
                phone_hint=payload["phone_hint"],
                username_hint=payload["username_hint"],
                validation_code=payload["validation_code"],
                validation_message=payload["validation_message"],
                risk_level=payload["risk_level"],
                created_at=utc_now(),
                updated_at=utc_now(),
            )
        )
    batch.item_count = len(items)
    batch.status = "preview_ready"
    batch.completed_at = utc_now()
    record_sensitive_audit_event(
        session,
        workspace_id=batch.workspace_id,
        actor_user_id=batch.created_by_user_id,
        action="account.import.validated",
        entity_type="account_import_batch",
        entity_id=batch.id,
        metadata={"item_count": batch.item_count, "source_type": batch.source_type},
    )
    session.commit()
    session.refresh(batch)
    return batch


def confirm_import_batch(
    session: Session,
    *,
    batch_id: str,
    workspace_id: str,
    confirmation: str,
) -> AccountImportBatch:
    batch = _require_batch(session, batch_id, workspace_id)
    if confirmation != "IMPORT":
        raise AppError(
            status_code=400,
            error_code="IMPORT_CONFIRMATION_REQUIRED",
            error_class="validation",
            message="confirmation must be IMPORT",
        )
    batch.status = "ready_for_import" if batch.dry_run else "importing"
    record_sensitive_audit_event(
        session,
        workspace_id=batch.workspace_id,
        actor_user_id=batch.created_by_user_id,
        action="account.import.confirmed",
        entity_type="account_import_batch",
        entity_id=batch.id,
        metadata={"dry_run": batch.dry_run, "item_count": batch.item_count},
    )
    session.commit()
    session.refresh(batch)
    return batch


def list_import_batches(
    session: Session, *, workspace_id: str, limit: int = 50
) -> list[AccountImportBatch]:
    return list(
        session.execute(
            select(AccountImportBatch)
            .where(AccountImportBatch.workspace_id == workspace_id)
            .order_by(AccountImportBatch.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def get_import_batch(
    session: Session, *, batch_id: str, workspace_id: str
) -> AccountImportBatch | None:
    return (
        session.execute(
            select(AccountImportBatch).where(
                AccountImportBatch.id == batch_id, AccountImportBatch.workspace_id == workspace_id
            )
        )
        .scalars()
        .first()
    )


def import_batch_to_dict(batch: AccountImportBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "workspace_id": batch.workspace_id,
        "source_type": batch.source_type,
        "status": batch.status,
        "label": batch.label,
        "dry_run": batch.dry_run,
        "item_count": batch.item_count,
        "created_at": _aware_utc(batch.created_at),
        "completed_at": _aware_utc(batch.completed_at),
        "failed_at": _aware_utc(batch.failed_at),
        "failure_code": batch.failure_code,
        "failure_message": batch.failure_message,
        "items": [import_item_to_dict(item) for item in batch.items],
    }


def import_item_to_dict(item: AccountImportItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "account_id": item.account_id,
        "status": item.status,
        "phone_hint": item.phone_hint,
        "username_hint": item.username_hint,
        "validation_code": item.validation_code,
        "validation_message": item.validation_message,
        "risk_level": item.risk_level,
        "created_at": _aware_utc(item.created_at),
        "updated_at": _aware_utc(item.updated_at),
    }


def _require_batch(session: Session, batch_id: str, workspace_id: str) -> AccountImportBatch:
    batch = get_import_batch(session, batch_id=batch_id, workspace_id=workspace_id)
    if batch is None:
        raise AppError(
            status_code=404,
            error_code="IMPORT_BATCH_NOT_FOUND",
            error_class="not_found",
            message="import batch not found",
        )
    return batch


def metadata_to_bytes(metadata: dict[str, Any] | None) -> bytes | None:
    if metadata is None:
        return None
    return json.dumps(metadata, sort_keys=True, default=str).encode("utf-8")


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)
