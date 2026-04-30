from __future__ import annotations

import socket
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.orm import Session

from app.models import AccountProxy
from app.services.accounts import get_account
from app.services.operation_logs import log_operation
from app.services.proxy_accounts import proxy_to_dict


class ProxyConnectivityChecker(Protocol):
    def check(self, proxy: AccountProxy) -> tuple[bool, str | None, str | None]:
        """Return ok, error_code, error_message for a technical proxy connectivity check."""


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
        except OSError as exc:
            return False, "proxy_connection_failed", str(exc)


def check_account_proxy(
    session: Session,
    account_id: str,
    *,
    checker: ProxyConnectivityChecker | None = None,
) -> dict:
    if get_account(session, account_id) is None:
        raise ValueError("account not found")
    proxy = session.get(AccountProxy, account_id)
    if proxy is None:
        raise ValueError("proxy not configured")
    ok, error_code, error_message = (checker or TcpProxyConnectivityChecker()).check(proxy)
    proxy.status = "working" if ok else "failed"
    proxy.last_checked_at = datetime.now(UTC)
    proxy.last_error_code = None if ok else error_code
    proxy.last_error_message = None if ok else error_message
    log_operation(
        session,
        account_id=account_id,
        operation_type="proxy",
        operation_key="check_proxy",
        status="completed" if ok else "failed",
        severity="info" if ok else "warning",
        source="proxy_check",
        message="Proxy check succeeded" if ok else "Proxy check failed",
        error_code=None if ok else error_code,
        error_class=None if ok else "proxy",
        metadata={"proxy_type": proxy.proxy_type, "host": proxy.host, "port": proxy.port},
    )
    session.commit()
    session.refresh(proxy)
    return proxy_to_dict(proxy)
