from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AccountOperationLog, new_id, utc_now
from app.services.accounts import get_account

SENSITIVE_KEYS = {"password", "password_encrypted", "token", "secret", "api_hash", "tdlib_api_hash"}


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
) -> AccountOperationLog:
    row = AccountOperationLog(
        id=new_id(),
        account_id=account_id,
        operation_type=operation_type,
        operation_key=operation_key,
        status=status,
        severity=severity,
        source=source,
        message=message,
        error_code=error_code,
        error_class=error_class,
        metadata_json=_sanitize(metadata or {}),
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
) -> dict[str, Any]:
    if get_account(session, account_id) is None:
        raise ValueError("account not found")
    return _list_logs(
        session,
        account_id=account_id,
        operation_type=operation_type,
        status=status,
        limit=limit,
        offset=offset,
    )


def list_global_logs(
    session: Session,
    *,
    account_id: str | None = None,
    operation_type: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    return _list_logs(
        session,
        account_id=account_id,
        operation_type=operation_type,
        status=status,
        limit=limit,
        offset=offset,
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
) -> dict[str, Any]:
    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)
    query = select(AccountOperationLog)
    count_query = select(func.count(AccountOperationLog.id))
    if account_id:
        query = query.where(AccountOperationLog.account_id == account_id)
        count_query = count_query.where(AccountOperationLog.account_id == account_id)
    if operation_type:
        query = query.where(AccountOperationLog.operation_type == operation_type)
        count_query = count_query.where(AccountOperationLog.operation_type == operation_type)
    if status:
        query = query.where(AccountOperationLog.status == status)
        count_query = count_query.where(AccountOperationLog.status == status)

    rows = session.execute(
        query.order_by(AccountOperationLog.created_at.desc()).offset(safe_offset).limit(safe_limit)
    ).scalars().all()
    total = int(session.execute(count_query).scalar_one())
    return {
        "items": [operation_log_to_dict(row) for row in rows],
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
    }


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in SENSITIVE_KEYS:
                result[key] = "***"
            else:
                result[key] = _sanitize(item)
        return result
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value
