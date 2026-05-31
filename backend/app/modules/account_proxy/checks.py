from __future__ import annotations

from datetime import datetime
import socket
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.adapters.tdlib_readonly_validity import (
    build_tdlib_readonly_validity_adapter,
)
from app.config import Settings, settings
from app.models import AccountProxy, utc_now
from app.modules.account_shared.interfaces import lookup_account
from app.modules.account_proxy.accounts import proxy_to_dict
from app.services.operation_logs import log_operation


class ProxyConnectivityChecker(Protocol):
    def check(self, proxy: AccountProxy) -> tuple[bool, str | None, str | None]:
        """Return ok, error_code, error_message for a technical proxy connectivity check."""
        ...


class TdlibProxyChecker(Protocol):
    def check_account(self, account_id: str) -> dict[str, Any]: ...


class TcpProxyConnectivityChecker:
    def __init__(self, timeout_seconds: float = 3.0) -> None:
        self._timeout_seconds = timeout_seconds

    def check(self, proxy: AccountProxy) -> tuple[bool, str | None, str | None]:
        try:
            with socket.create_connection((proxy.host, proxy.port), timeout=self._timeout_seconds):
                return True, None, None
        except socket.timeout:
            return False, "proxy_timeout", "Proxy connection timed out"
        except socket.gaierror:
            return False, "proxy_dns_failed", "Proxy host could not be resolved"
        except ConnectionRefusedError:
            return False, "proxy_connection_refused", "Proxy refused the connection"
        except OSError:
            return False, "proxy_connection_failed", "Proxy connection failed"


def check_account_proxy(
    session: Session,
    account_id: str,
    *,
    checker: ProxyConnectivityChecker | None = None,
    tdlib_checker: TdlibProxyChecker | None = None,
    config: Settings = settings,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    if lookup_account(session, account_id, workspace_id=workspace_id) is None:
        raise ValueError("account not found")
    proxy = session.get(AccountProxy, account_id)
    if proxy is None:
        raise ValueError("proxy not configured")
    ok, error_code, error_message = (checker or TcpProxyConnectivityChecker()).check(proxy)
    check_scope = "tcp"
    now = utc_now()
    status = "tcp_working" if ok else "failed"
    tdlib_error_code = None
    tdlib_error_message = None
    tdlib_verified_at = proxy.tdlib_verified_at
    if ok and _should_run_tdlib_proxy_check(config):
        check_scope = "tcp_tdlib"
        status, tdlib_error_code, tdlib_error_message, tdlib_verified_at = (
            _tdlib_proxy_check_state(
                account_id,
                config=config,
                tdlib_checker=tdlib_checker,
                now=now,
                previous_verified_at=proxy.tdlib_verified_at,
            )
        )
    proxy.status = status
    proxy.last_checked_at = now
    proxy.last_check_scope = check_scope
    proxy.last_error_code = None if ok else error_code
    proxy.last_error_message = None if ok else error_message
    proxy.tdlib_verified_at = tdlib_verified_at
    proxy.tdlib_last_error_code = tdlib_error_code
    proxy.tdlib_last_error_message = tdlib_error_message
    log_operation(
        session,
        account_id=account_id,
        operation_type="proxy",
        operation_key="check_proxy",
        status="completed"
        if status in {"tcp_working", "tdlib_working", "tdlib_unverified"}
        else "failed",
        severity="info" if status in {"tcp_working", "tdlib_working"} else "warning",
        source="proxy_check",
        message=_proxy_check_message(status),
        error_code=None
        if ok and status != "tdlib_failed"
        else (tdlib_error_code if status == "tdlib_failed" else error_code),
        error_class="tdlib_proxy" if status == "tdlib_failed" else (None if ok else "proxy"),
        workspace_id=workspace_id,
        metadata={
            "proxy_type": proxy.proxy_type,
            "host": proxy.host,
            "port": proxy.port,
            "check_scope": check_scope,
            "tdlib_status": status if check_scope == "tcp_tdlib" else None,
            "tdlib_error_code": tdlib_error_code,
        },
    )
    session.commit()
    session.refresh(proxy)
    return proxy_to_dict(proxy)


def _should_run_tdlib_proxy_check(config: Settings) -> bool:
    return bool(
        config.profile_execution_adapter == "tdlib"
        and config.tdlib_api_id
        and config.tdlib_api_hash
    )


def _tdlib_proxy_check_state(
    account_id: str,
    *,
    config: Settings,
    tdlib_checker: TdlibProxyChecker | None,
    now: datetime,
    previous_verified_at: datetime | None,
) -> tuple[str, str | None, str | None, datetime | None]:
    tdlib_result = (tdlib_checker or build_tdlib_readonly_validity_adapter(config)).check_account(
        account_id
    )
    tdlib_status = str(tdlib_result.get("status") or "unknown")
    if tdlib_status == "valid":
        return "tdlib_working", None, None, now
    if tdlib_status in {"reauth_required", "awaiting_code", "awaiting_password", "unknown"}:
        return (
            "tdlib_unverified",
            str(tdlib_result.get("error_code") or tdlib_status),
            str(tdlib_result.get("error") or tdlib_result.get("runtime_health") or tdlib_status),
            previous_verified_at,
        )
    return (
        "tdlib_failed",
        str(tdlib_result.get("error_code") or "tdlib_proxy_check_failed"),
        str(
            tdlib_result.get("error")
            or tdlib_result.get("runtime_health")
            or "TDLib proxy check failed"
        ),
        previous_verified_at,
    )


def _proxy_check_message(status: str) -> str:
    return {
        "tcp_working": "TCP proxy check succeeded",
        "tdlib_working": "TDLib proxy check succeeded",
        "tdlib_unverified": (
            "TCP proxy works, but Telegram account is not ready for TDLib verification"
        ),
        "tdlib_failed": "TDLib proxy check failed",
        "failed": "Proxy check failed",
    }.get(status, "Proxy check completed")
