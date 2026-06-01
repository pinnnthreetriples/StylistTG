from __future__ import annotations

import time
from typing import Any, Callable

from app.adapters.tdlib_auth import (
    RealTdJsonClientFactory,
    TdlibAuthStatus,
    TdlibClient,
    TdlibClientFactory,
    UnavailableTdlibClientFactory,
    extract_authorization_state,
    map_authorization_state,
    map_tdlib_error,
    tdlib_parameters_query,
)
from app.config import Settings, settings
from app.services.tdlib_proxy import apply_account_proxy_to_tdlib


class TdlibReadOnlyValidityAdapter:
    """Read-only TDLib account check. Never submits auth codes or write queries."""

    def __init__(
        self,
        *,
        client_factory: TdlibClientFactory,
        config: Settings = settings,
        proxy_applier: Callable[[TdlibClient, str], bool] | None = None,
    ) -> None:
        self._client_factory = client_factory
        self._config = config
        self._proxy_applier = proxy_applier

    def check_account(self, account_id: str) -> dict[str, Any]:
        if not self._config.tdlib_api_id or not self._config.tdlib_api_hash:
            return _missing_credentials_result()
        client = None
        try:
            client = self._client_factory.create(account_id)
            proxy_applied = False
            deadline = time.monotonic() + self._config.tdlib_auth_timeout_seconds
            while time.monotonic() < deadline:
                event = client.receive(self._config.tdlib_receive_timeout_seconds)
                if event and event.get("@type") == "error":
                    return _tdlib_error_result(event)
                state = extract_authorization_state(event)
                if state is None:
                    continue
                mapped = map_authorization_state(state)
                if mapped.status == TdlibAuthStatus.WAIT_TDLIB_PARAMETERS:
                    client.send(tdlib_parameters_query(self._config, account_id))
                    if self._proxy_applier is not None and not proxy_applied:
                        self._proxy_applier(client, account_id)
                        proxy_applied = True
                    continue
                if mapped.status == TdlibAuthStatus.READY:
                    me = client.send_query(
                        {"@type": "getMe"}, self._config.tdlib_receive_timeout_seconds
                    )
                    return _valid_profile_result(me)
                if mapped.status in {
                    TdlibAuthStatus.WAIT_PHONE_NUMBER,
                    TdlibAuthStatus.WAIT_CODE,
                    TdlibAuthStatus.WAIT_PASSWORD,
                }:
                    return _auth_state_result("reauth_required", mapped, "auth_state")
                if mapped.status == TdlibAuthStatus.BROKEN:
                    return _auth_state_result("runtime_broken", mapped, "runtime")
                return _auth_state_result("unknown", mapped, "auth_state")
            return _timeout_result()
        except Exception:
            return _runtime_error_result()
        finally:
            if client is not None:
                client.close()


def build_tdlib_readonly_validity_adapter(
    config: Settings = settings,
) -> TdlibReadOnlyValidityAdapter:
    try:
        factory: TdlibClientFactory = RealTdJsonClientFactory(config.tdlib_shared_library_path)
    except OSError as exc:
        factory = UnavailableTdlibClientFactory(str(exc))
    return TdlibReadOnlyValidityAdapter(
        client_factory=factory,
        config=config,
        proxy_applier=lambda client, account_id: apply_account_proxy_to_tdlib(
            client, account_id, config=config
        ),
    )


def _missing_credentials_result() -> dict[str, Any]:
    return {
        "status": "runtime_broken",
        "runtime_health": "missing_tdlib_credentials",
        "error_code": "missing_tdlib_credentials",
        "error_class": "configuration",
    }


def _tdlib_error_result(event: dict[str, Any]) -> dict[str, Any]:
    mapped = map_tdlib_error(event)
    return {
        "status": "runtime_broken" if mapped.runtime_health == "tdlib_error" else "reauth_required",
        "runtime_health": mapped.runtime_health,
        "error_code": mapped.recovery_marker,
        "error_class": "tdlib_error",
        "error": mapped.error,
    }


def _valid_profile_result(me: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "valid",
        "runtime_health": "ready",
        "telegram_user_id": str(me.get("id")) if me.get("id") is not None else None,
        "profile": {
            "first_name": me.get("first_name"),
            "last_name": me.get("last_name"),
            "username": me.get("username"),
        },
    }


def _auth_state_result(status: str, mapped: Any, error_class: str) -> dict[str, Any]:
    result = {
        "status": status,
        "runtime_health": mapped.runtime_health,
        "error_code": mapped.recovery_marker,
        "error_class": error_class,
    }
    if mapped.error is not None:
        result["error"] = mapped.error
    return result


def _timeout_result() -> dict[str, Any]:
    return {
        "status": "unknown",
        "runtime_health": "timeout",
        "error_code": "tdlib_readonly_timeout",
        "error_class": "timeout",
    }


def _runtime_error_result() -> dict[str, Any]:
    return {
        "status": "runtime_broken",
        "runtime_health": "broken",
        "error_code": "tdlib_readonly_runtime_broken",
        "error_class": "runtime",
        "error": "internal_error",
    }
