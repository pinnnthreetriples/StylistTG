"""Runtime refresh + diagnostics composition shared across feature modules.

Owns the runtime refresh/diagnostics business logic so both the
canonical safety runtime router and the legacy header-based compat
router in `account_core` can delegate here without taking a direct
account_core <-> account_safety dependency.
"""

from __future__ import annotations

from datetime import UTC, datetime
from http import HTTPStatus

from sqlalchemy.orm import Session

from app.adapters.tdlib_profile_execution import build_profile_execution_adapter
from app.errors import AppError
from app.logging_utils import log_event
from app.modules.account_profile_state.interfaces import (
    build_profile_sync_adapter,
    sync_account_profile_snapshot,
)
from app.schemas import AccountRuntimeDiagnosticsRead, RuntimeRefreshRead
from app.services.execution_policy import ensure_execution_usable
from app.services.operation_logs import log_operation
from app.services.runtime_diagnostics import account_runtime_diagnostics


def refresh_account_runtime(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
) -> RuntimeRefreshRead:
    """Refresh runtime for `account_id` and return the public read model.

    Pure business logic — callers (HTTP routers) own auth/workspace
    checks before invoking this.
    """
    try:
        log_event("runtime_refresh_requested", account_id=account_id)
        result = ensure_execution_usable(
            session,
            account_id,
            adapter=build_profile_execution_adapter(),
        )
    except ValueError as exc:
        raise AppError(
            status_code=HTTPStatus.NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message=str(exc),
        ) from exc
    if result.account.account_state == "execution_usable":
        profile_sync_adapter = build_profile_sync_adapter()
        try:
            sync_account_profile_snapshot(session, account_id, adapter=profile_sync_adapter)
            log_operation(
                session,
                account_id=account_id,
                operation_type="sync",
                operation_key="profile_snapshot",
                status="completed",
                severity="info",
                source="runtime_refresh",
                message="Profile snapshot synced",
                workspace_id=workspace_id,
            )
            session.commit()
        except Exception as exc:
            session.rollback()
            log_operation(
                session,
                account_id=account_id,
                operation_type="sync",
                operation_key="profile_snapshot",
                status="failed",
                severity="warning",
                source="runtime_refresh",
                message="Profile snapshot sync failed",
                error_code="PROFILE_SYNC_FAILED",
                error_class=exc.__class__.__name__,
                workspace_id=workspace_id,
            )
            session.commit()
            log_event(
                "profile_sync_failed",
                account_id=account_id,
                error_class=exc.__class__.__name__,
            )
            raise AppError(
                status_code=HTTPStatus.BAD_GATEWAY,
                error_code="PROFILE_SYNC_FAILED",
                error_class="telegram_sync",
                message="Telegram profile sync failed",
                details={"reason": exc.__class__.__name__},
            ) from exc
    diagnostics = account_runtime_diagnostics(session, account_id)
    return RuntimeRefreshRead(
        account_id=result.account.id,
        account_state=result.account.account_state,
        runtime_health=result.runtime_state.runtime_health,
        is_execution_usable=result.account.account_state == "execution_usable",
        last_error_code=diagnostics["last_error_code"],
        last_error_class=diagnostics["last_error_class"],
        refreshed_at=datetime.now(UTC),
    )


def get_runtime_diagnostics(session: Session, account_id: str) -> AccountRuntimeDiagnosticsRead:
    """Return the public runtime diagnostics read model for `account_id`."""
    try:
        payload = account_runtime_diagnostics(session, account_id)
    except ValueError as exc:
        raise AppError(
            status_code=HTTPStatus.NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message=str(exc),
        ) from exc
    return AccountRuntimeDiagnosticsRead(**payload)


__all__ = ["get_runtime_diagnostics", "refresh_account_runtime"]
