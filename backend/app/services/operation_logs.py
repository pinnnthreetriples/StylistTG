from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DEFAULT_LOCAL_WORKSPACE_ID, AccountOperationLog, new_id, utc_now
from app.services.accounts import get_account
from app.services.secret_redaction import redact_metadata


def log_operation(
    session: Session,
    *,
    account_id: str,
    operation_type: str,
    status: str,
    source: str,
    message: str,
    severity: str = "info",
    operation_key: str | None = None,
    error_code: str | None = None,
    error_class: str | None = None,
    metadata: dict[str, Any] | None = None,
    request_id: str | None = None,
    job_id: str | None = None,
    step_id: str | None = None,
    created_at: datetime | None = None,
    workspace_id: str | None = None,
) -> AccountOperationLog:
    resolved_workspace_id = workspace_id
    if resolved_workspace_id is None:
        resolved_workspace_id = getattr(
            get_account(session, account_id), "workspace_id", DEFAULT_LOCAL_WORKSPACE_ID
        )
    row = AccountOperationLog(
        id=new_id(),
        workspace_id=resolved_workspace_id,
        account_id=account_id,
        operation_type=operation_type,
        operation_key=operation_key,
        status=status,
        severity=severity,
        source=source,
        message=message,
        error_code=error_code,
        error_class=error_class,
        metadata_json=redact_metadata(metadata or {}),
        request_id=request_id,
        job_id=job_id,
        step_id=step_id,
        created_at=created_at or utc_now(),
    )
    session.add(row)
    return row


def list_account_logs(
    session: Session,
    account_id: str,
    *,
    operation_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    if get_account(session, account_id, workspace_id=workspace_id) is None:
        raise ValueError("account not found")
    return _list_logs(
        session,
        account_id=account_id,
        operation_type=operation_type,
        status=status,
        limit=limit,
        offset=offset,
        workspace_id=workspace_id,
    )


def list_global_logs(
    session: Session,
    *,
    account_id: str | None = None,
    operation_type: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    return _list_logs(
        session,
        account_id=account_id,
        operation_type=operation_type,
        status=status,
        limit=limit,
        offset=offset,
        workspace_id=workspace_id,
    )


def operation_log_to_dict(row: AccountOperationLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "account_id": row.account_id,
        "operation_type": row.operation_type,
        "operation_key": row.operation_key,
        "status": row.status,
        "severity": row.severity,
        "source": row.source,
        "message": row.message,
        "error_code": row.error_code,
        "error_class": row.error_class,
        "metadata": row.metadata_json or {},
        "request_id": row.request_id,
        "job_id": row.job_id,
        "step_id": row.step_id,
        "created_at": row.created_at,
    }


def _list_logs(
    session: Session,
    *,
    account_id: str | None,
    operation_type: str | None,
    status: str | None,
    limit: int,
    offset: int,
    workspace_id: str | None,
) -> dict[str, Any]:
    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)
    query = select(AccountOperationLog)
    count_query = select(func.count(AccountOperationLog.id))
    if workspace_id:
        query = query.where(AccountOperationLog.workspace_id == workspace_id)
        count_query = count_query.where(AccountOperationLog.workspace_id == workspace_id)
    if account_id:
        query = query.where(AccountOperationLog.account_id == account_id)
        count_query = count_query.where(AccountOperationLog.account_id == account_id)
    if operation_type:
        query = query.where(AccountOperationLog.operation_type == operation_type)
        count_query = count_query.where(AccountOperationLog.operation_type == operation_type)
    if status:
        query = query.where(AccountOperationLog.status == status)
        count_query = count_query.where(AccountOperationLog.status == status)

    rows = (
        session.execute(
            query.order_by(AccountOperationLog.created_at.desc())
            .offset(safe_offset)
            .limit(safe_limit)
        )
        .scalars()
        .all()
    )
    total = int(session.execute(count_query).scalar_one())
    return {
        "items": [operation_log_to_dict(row) for row in rows],
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
    }
