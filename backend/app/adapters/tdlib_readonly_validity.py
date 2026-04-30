from __future__ import annotations

import time
from typing import Any, Callable

from app.adapters.tdlib_auth import (
    RealTdJsonClientFactory,
    TdlibAuthStatus,
    TdlibClient,
    TdlibClientFactory,
    UnavailableTdlibClientFactory,
    _extract_authorization_state,
    _tdlib_parameters_query,
    map_authorization_state,
    map_tdlib_error,
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
            return {
                "status": "runtime_broken",
                "runtime_health": "missing_tdlib_credentials",
                "error_code": "missing_tdlib_credentials",
                "error_class": "configuration",
            }
        client = None
        try:
            client = self._client_factory.create(account_id)
            proxy_applied = False
            deadline = time.monotonic() + self._config.tdlib_auth_timeout_seconds
            while time.monotonic() < deadline:
                event = client.receive(self._config.tdlib_receive_timeout_seconds)
                if event and event.get("@type") == "error":
                    mapped = map_tdlib_error(event)
                    return {
                        "status": "runtime_broken" if mapped.runtime_health == "tdlib_error" else "reauth_required",
                        "runtime_health": mapped.runtime_health,
                        "error_code": mapped.recovery_marker,
                        "error_class": "tdlib_error",
                        "error": mapped.error,
                    }
                state = _extract_authorization_state(event)
                if state is None:
                    continue
                mapped = map_authorization_state(state)
                if mapped.status == TdlibAuthStatus.WAIT_TDLIB_PARAMETERS:
                    client.send(_tdlib_parameters_query(self._config, account_id))
                    if self._proxy_applier is not None and not proxy_applied:
                        self._proxy_applier(client, account_id)
                        proxy_applied = True
                    continue
                if mapped.status == TdlibAuthStatus.READY:
                    me = client.send_query({"@type": "getMe"}, self._config.tdlib_receive_timeout_seconds)
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
                if mapped.status in {TdlibAuthStatus.WAIT_PHONE_NUMBER, TdlibAuthStatus.WAIT_CODE, TdlibAuthStatus.WAIT_PASSWORD}:
                    return {
                        "status": "reauth_required",
                        "runtime_health": mapped.runtime_health,
                        "error_code": mapped.recovery_marker,
                        "error_class": "auth_state",
                    }
                if mapped.status == TdlibAuthStatus.BROKEN:
                    return {
                        "status": "runtime_broken",
                        "runtime_health": mapped.runtime_health,
                        "error_code": mapped.recovery_marker,
                        "error_class": "runtime",
                        "error": mapped.error,
                    }
                return {
                    "status": "unknown",
                    "runtime_health": mapped.runtime_health,
                    "error_code": mapped.recovery_marker,
                    "error_class": "auth_state",
                }
            return {
                "status": "unknown",
                "runtime_health": "timeout",
                "error_code": "tdlib_readonly_timeout",
                "error_class": "timeout",
            }
        except Exception as exc:
            return {
                "status": "runtime_broken",
                "runtime_health": "broken",
                "error_code": "tdlib_readonly_runtime_broken",
                "error_class": exc.__class__.__name__,
                "error": str(exc),
            }
        finally:
            if client is not None:
                client.close()


def build_tdlib_readonly_validity_adapter(config: Settings = settings) -> TdlibReadOnlyValidityAdapter:
    try:
        factory: TdlibClientFactory = RealTdJsonClientFactory(config.tdlib_shared_library_path)
    except OSError as exc:
        factory = UnavailableTdlibClientFactory(str(exc))
    return TdlibReadOnlyValidityAdapter(
        client_factory=factory,
        config=config,
        proxy_applier=lambda client, account_id: apply_account_proxy_to_tdlib(client, account_id, config=config),
    )
