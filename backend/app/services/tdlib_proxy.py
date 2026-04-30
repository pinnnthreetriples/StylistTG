from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.config import Settings, settings
from app.db import SessionLocal
from app.models import AccountProxy
from app.services.operation_logs import log_operation
from app.services.proxy_accounts import decrypt_proxy_password


class TdlibProxyClient(Protocol):
    def send_query(self, query: dict, timeout_seconds: float) -> dict: ...


@dataclass(frozen=True)
class TdlibProxySettings:
    proxy_type: str
    host: str
    port: int
    username: str | None = None
    password: str | None = None


def resolve_tdlib_proxy_settings(
    account_id: str,
    *,
    config: Settings = settings,
) -> TdlibProxySettings | None:
    with SessionLocal() as session:
        row = session.get(AccountProxy, account_id)
        if row is None:
            return None
        return TdlibProxySettings(
            proxy_type=row.proxy_type,
            host=row.host,
            port=row.port,
            username=row.username,
            password=decrypt_proxy_password(row, config=config),
        )


def apply_account_proxy_to_tdlib(
    client: TdlibProxyClient,
    account_id: str,
    *,
    config: Settings = settings,
    proxy_settings: TdlibProxySettings | None = None,
) -> bool:
    proxy = proxy_settings if proxy_settings is not None else resolve_tdlib_proxy_settings(account_id, config=config)
    if proxy is None:
        return False
    _log_proxy_apply(account_id, status="started", message="TDLib proxy apply started", proxy=proxy)
    try:
        response = client.send_query(_add_proxy_query(proxy), config.tdlib_proxy_apply_timeout_seconds)
        if response.get("@type") == "error":
            raise RuntimeError(str(response.get("message") or "TDLib addProxy failed"))
        proxy_id = response.get("id")
        if proxy_id is None:
            raise RuntimeError("TDLib addProxy did not return proxy id")
        enable_response = client.send_query(
            {"@type": "enableProxy", "proxy_id": int(proxy_id)},
            config.tdlib_proxy_apply_timeout_seconds,
        )
        if enable_response.get("@type") == "error":
            raise RuntimeError(str(enable_response.get("message") or "TDLib enableProxy failed"))
        _log_proxy_apply(account_id, status="completed", message="TDLib proxy apply completed", proxy=proxy)
        return True
    except Exception as exc:
        _log_proxy_apply(
            account_id,
            status="failed",
            message="TDLib proxy apply failed",
            proxy=proxy,
            error_code="tdlib_proxy_apply_failed",
            error_class=exc.__class__.__name__,
        )
        raise


def _add_proxy_query(proxy: TdlibProxySettings) -> dict:
    return {
        "@type": "addProxy",
        "server": proxy.host,
        "port": proxy.port,
        "enable": True,
        "type": _proxy_type_query(proxy),
    }


def _proxy_type_query(proxy: TdlibProxySettings) -> dict:
    credentials = {
        "username": proxy.username or "",
        "password": proxy.password or "",
    }
    if proxy.proxy_type == "http":
        return {"@type": "proxyTypeHttp", **credentials, "http_only": False}
    if proxy.proxy_type == "socks5":
        return {"@type": "proxyTypeSocks5", **credentials}
    raise ValueError("proxy_unsupported")


def _log_proxy_apply(
    account_id: str,
    *,
    status: str,
    message: str,
    proxy: TdlibProxySettings,
    error_code: str | None = None,
    error_class: str | None = None,
) -> None:
    with SessionLocal() as session:
        log_operation(
            session,
            account_id=account_id,
            operation_type="proxy",
            operation_key="tdlib_apply_proxy",
            status=status,
            severity="error" if status == "failed" else "info",
            source="tdlib_proxy",
            message=message,
            error_code=error_code,
            error_class=error_class,
            metadata={
                "proxy_type": proxy.proxy_type,
                "host": proxy.host,
                "port": proxy.port,
                "has_username": bool(proxy.username),
                "has_password": bool(proxy.password),
            },
        )
        session.commit()
