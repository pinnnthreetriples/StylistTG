from __future__ import annotations

from typing import Callable

from app.adapters.tdlib_auth import (
    RealTdJsonClientFactory,
    TdlibAuthStatus,
    TdlibClient,
    TdlibClientFactory,
    extract_authorization_state,
    map_authorization_state,
    tdlib_parameters_query,
)
from app.config import Settings, settings
from app.services.neuro_commenting.errors import NeuroRuntimeUnavailableError
from app.services.tdlib_client import safe_tdlib_error_message
from app.services.tdlib_proxy import apply_account_proxy_to_tdlib


class NeuroTdlibRuntime:
    def __init__(
        self,
        *,
        config: Settings = settings,
        client_factory: TdlibClientFactory | None = None,
        proxy_applier: Callable[[TdlibClient, str], bool] | None = None,
    ) -> None:
        self._config = config
        self._client_factory = client_factory
        self._proxy_applier: Callable[[TdlibClient, str], bool] = (
            proxy_applier if proxy_applier is not None else self._apply_account_proxy
        )
        self._factory_error: Exception | None = None

    def ready_client(self, account_id: str) -> TdlibClient:
        try:
            client = self._factory().create(account_id)
            self._ensure_ready(client, account_id)
            return client
        except NeuroRuntimeUnavailableError:
            raise
        except Exception as exc:
            raise NeuroRuntimeUnavailableError(
                "TDLib runtime is unavailable", error_code="TDLIB_RUNTIME_UNAVAILABLE"
            ) from exc

    def _factory(self) -> TdlibClientFactory:
        if self._client_factory is not None:
            return self._client_factory
        if self._factory_error is not None:
            raise NeuroRuntimeUnavailableError(
                "TDLib runtime is unavailable", error_code="TDLIB_RUNTIME_UNAVAILABLE"
            )
        try:
            self._client_factory = RealTdJsonClientFactory(self._config.tdlib_shared_library_path)
        except Exception as exc:
            self._factory_error = exc
            raise NeuroRuntimeUnavailableError(
                "TDLib runtime is unavailable", error_code="TDLIB_RUNTIME_UNAVAILABLE"
            ) from exc
        return self._client_factory

    def _ensure_ready(self, client: TdlibClient, account_id: str) -> None:
        proxy_applied = False
        deadline_loops = max(1, int(self._config.tdlib_auth_timeout_seconds * 2))
        saw_auth_state = False
        for _ in range(deadline_loops):
            event = client.receive(self._config.tdlib_receive_timeout_seconds)
            if event is None:
                continue
            if event.get("@type") == "error":
                raise _runtime_error_from_tdlib(event)
            state = extract_authorization_state(event)
            if state is None:
                continue
            saw_auth_state = True
            mapped = map_authorization_state(state)
            if mapped.status == TdlibAuthStatus.WAIT_TDLIB_PARAMETERS:
                client.send(tdlib_parameters_query(self._config, account_id))
                if not proxy_applied:
                    self._proxy_applier(client, account_id)
                    proxy_applied = True
                continue
            if mapped.status == TdlibAuthStatus.READY:
                self._check_get_me(client)
                return
            if mapped.status in {
                TdlibAuthStatus.WAIT_PHONE_NUMBER,
                TdlibAuthStatus.WAIT_CODE,
                TdlibAuthStatus.WAIT_PASSWORD,
            }:
                raise NeuroRuntimeUnavailableError(
                    "TDLib account requires reauth", error_code="REAUTH_REQUIRED"
                )
            raise NeuroRuntimeUnavailableError(
                "TDLib runtime is unavailable",
                error_code=mapped.recovery_marker or "TDLIB_RUNTIME_UNAVAILABLE",
            )
        if saw_auth_state:
            raise NeuroRuntimeUnavailableError(
                "TDLib auth state did not converge", error_code="TDLIB_RUNTIME_UNAVAILABLE"
            )
        self._check_get_me(client)

    def _check_get_me(self, client: TdlibClient) -> None:
        try:
            response = client.send_query(
                {"@type": "getMe"}, self._config.tdlib_receive_timeout_seconds
            )
        except Exception as exc:
            raise NeuroRuntimeUnavailableError(
                safe_tdlib_error_message(exc), error_code="TDLIB_RUNTIME_UNAVAILABLE"
            ) from exc
        if response.get("@type") == "error":
            raise _runtime_error_from_tdlib(response)

    def _apply_account_proxy(self, client: TdlibClient, account_id: str) -> bool:
        return apply_account_proxy_to_tdlib(client, account_id, config=self._config)


def _runtime_error_from_tdlib(response: dict[str, object]) -> NeuroRuntimeUnavailableError:
    message = str(response.get("message") or "")
    upper = message.upper()
    if "UNAUTHORIZED" in upper:
        return NeuroRuntimeUnavailableError(
            "TDLib account is unauthorized", error_code="TDLIB_UNAUTHORIZED"
        )
    return NeuroRuntimeUnavailableError(
        safe_tdlib_error_message(response), error_code="TDLIB_RUNTIME_UNAVAILABLE"
    )
