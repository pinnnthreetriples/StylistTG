from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.db import get_session
from app.errors import AppError
from app.modules.account_proxy.accounts import (
    delete_account_proxy,
    get_account_proxy,
    proxy_summary,
    upsert_account_proxy,
)
from app.modules.account_proxy.checks import check_account_proxy
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import (
    require_authenticated,
    require_mutation_permission,
)
from app.modules.warmup.service import warmup_operation_policy
from app.schemas import (
    AccountProxyRead,
    AccountProxySummaryRead,
    AccountProxyUpsert,
)

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

SAFE_PROXY_VALIDATION_MESSAGES = {
    "proxy_credentials_key_required",
    "proxy_credentials_crypto_unavailable",
    "proxy_unsupported",
    "proxy_host_required",
    "proxy_port_invalid",
}


@router.get("/proxy-summary", response_model=list[AccountProxySummaryRead])
def get_accounts_proxy_summary(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    return proxy_summary(session, workspace_id=auth.workspace_id)


@router.get("/{account_id}/proxy", response_model=AccountProxyRead | None)
def get_account_proxy_endpoint(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    try:
        return get_account_proxy(session, account_id, workspace_id=auth.workspace_id)
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message=str(exc),
        ) from exc


@router.put("/{account_id}/proxy", response_model=AccountProxyRead)
def put_account_proxy(
    account_id: str,
    payload: AccountProxyUpsert,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    require_account_in_workspace(session, account_id, auth)
    _raise_if_warmup_locked(
        session,
        account_id=account_id,
        workspace_id=auth.workspace_id,
        operation="proxy_change",
    )
    try:
        return upsert_account_proxy(
            session,
            account_id,
            proxy_type=payload.proxy_type,
            host=payload.host,
            port=payload.port,
            username=payload.username,
            password=payload.password,
            workspace_id=auth.workspace_id,
        )
    except ValueError as exc:
        raise _proxy_error(exc) from exc


@router.delete("/{account_id}/proxy", status_code=status.HTTP_204_NO_CONTENT)
def delete_account_proxy_endpoint(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    require_account_in_workspace(session, account_id, auth)
    _raise_if_warmup_locked(
        session,
        account_id=account_id,
        workspace_id=auth.workspace_id,
        operation="proxy_change",
    )
    try:
        delete_account_proxy(session, account_id, workspace_id=auth.workspace_id)
    except ValueError as exc:
        raise _proxy_error(exc) from exc


@router.post("/{account_id}/proxy/check", response_model=AccountProxyRead)
def post_account_proxy_check(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    require_account_in_workspace(session, account_id, auth)
    try:
        return check_account_proxy(session, account_id, workspace_id=auth.workspace_id)
    except ValueError as exc:
        raise _proxy_error(exc, operation="check") from exc


def _proxy_error(exc: ValueError, *, operation: str = "operation") -> AppError:
    message = str(exc)
    if message == "account not found":
        return AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message=message,
        )
    if message == "proxy not configured":
        return AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="PROXY_NOT_CONFIGURED",
            error_class="not_found",
            message=message,
        )
    if message in SAFE_PROXY_VALIDATION_MESSAGES:
        return AppError(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=message.upper(),
            error_class="proxy",
            message=message,
        )
    return AppError(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_code="PROXY_CHECK_FAILED"
        if operation == "check"
        else "PROXY_OPERATION_FAILED",
        error_class="proxy",
        message="Proxy check failed"
        if operation == "check"
        else "Proxy operation failed",
    )


def _raise_if_warmup_locked(
    session: Session, *, account_id: str, workspace_id: str, operation: str
) -> None:
    policy = warmup_operation_policy(
        session,
        account_id=account_id,
        workspace_id=workspace_id,
        operation=operation,
    )
    if policy["is_locked"]:
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            error_code="ACCOUNT_WARMUP_LOCKED",
            error_class="state_conflict",
            message=policy["reason"],
        )


__all__ = ["router"]
