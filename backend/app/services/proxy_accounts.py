from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.models import AccountProxy
from app.services.accounts import get_account
from app.services.operation_logs import log_operation


SUPPORTED_PROXY_TYPES = {"socks5", "http"}


def get_account_proxy(session: Session, account_id: str) -> dict[str, Any] | None:
    if get_account(session, account_id) is None:
        raise ValueError("account not found")
    row = session.get(AccountProxy, account_id)
    return proxy_to_dict(row) if row else None


def proxy_summary(session: Session) -> list[dict[str, Any]]:
    rows = session.query(AccountProxy).all()
    return [
        {
            "account_id": row.account_id,
            "status": row.status,
            "proxy_type": row.proxy_type,
            "host": row.host,
            "port": row.port,
            "last_checked_at": row.last_checked_at,
            "last_error_code": row.last_error_code,
        }
        for row in rows
    ]


def upsert_account_proxy(
    session: Session,
    account_id: str,
    *,
    proxy_type: str,
    host: str,
    port: int,
    username: str | None,
    password: str | None,
    config: Settings = settings,
) -> dict[str, Any]:
    if get_account(session, account_id) is None:
        raise ValueError("account not found")
    _validate_proxy(proxy_type=proxy_type, host=host, port=port)
    encrypted_password = _encrypt_password(password, config=config) if password else None
    row = session.get(AccountProxy, account_id)
    if row is None:
        row = AccountProxy(account_id=account_id)
        session.add(row)
    row.proxy_type = proxy_type
    row.host = host.strip()
    row.port = port
    row.username = username.strip() if username else None
    if password is not None:
        row.password_encrypted = encrypted_password
    row.status = "unknown"
    row.last_error_code = None
    row.last_error_message = None
    log_operation(
        session,
        account_id=account_id,
        operation_type="proxy",
        operation_key="save_proxy",
        status="completed",
        severity="info",
        source="proxy_settings",
        message="Proxy settings saved",
        metadata={"proxy_type": proxy_type, "host": host, "port": port, "has_password": bool(password)},
    )
    session.commit()
    session.refresh(row)
    return proxy_to_dict(row)


def delete_account_proxy(session: Session, account_id: str) -> None:
    if get_account(session, account_id) is None:
        raise ValueError("account not found")
    row = session.get(AccountProxy, account_id)
    if row is not None:
        session.delete(row)
        log_operation(
            session,
            account_id=account_id,
            operation_type="proxy",
            operation_key="delete_proxy",
            status="completed",
            severity="info",
            source="proxy_settings",
            message="Proxy removed",
        )
    session.commit()


def proxy_to_dict(row: AccountProxy) -> dict[str, Any]:
    return {
        "account_id": row.account_id,
        "proxy_type": row.proxy_type,
        "host": row.host,
        "port": row.port,
        "username": _masked_username(row.username),
        "has_password": bool(row.password_encrypted),
        "status": row.status,
        "last_checked_at": row.last_checked_at,
        "last_error_code": row.last_error_code,
        "last_error_message": row.last_error_message,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _validate_proxy(*, proxy_type: str, host: str, port: int) -> None:
    if proxy_type not in SUPPORTED_PROXY_TYPES:
        raise ValueError("proxy_unsupported")
    if not host.strip():
        raise ValueError("proxy_host_required")
    if port < 1 or port > 65535:
        raise ValueError("proxy_port_invalid")


def _encrypt_password(password: str | None, *, config: Settings = settings) -> str | None:
    if not password:
        return None
    if not config.proxy_credentials_encryption_key:
        raise ValueError("proxy_credentials_key_required")
    try:
        from cryptography.fernet import Fernet
    except ModuleNotFoundError as exc:
        raise ValueError("proxy_credentials_crypto_unavailable") from exc
    token = Fernet(config.proxy_credentials_encryption_key.encode("utf-8")).encrypt(password.encode("utf-8"))
    return token.decode("utf-8")


def _masked_username(username: str | None) -> str | None:
    if not username:
        return None
    if len(username) <= 2:
        return username[0] + "*"
    return f"{username[0]}***{username[-1]}"
