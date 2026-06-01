from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Callable, cast

from app.adapters import tdlib_json_client as _tdlib_json_client
from app.adapters.tdlib_auth_states import (
    JsonDict,
    TdlibAuthResult,
    TdlibAuthStatus,
    broken_tdlib_runtime_result,
    map_authorization_state,
    map_tdlib_error,
    missing_tdlib_credentials_result,
    tdlib_auth_timeout_result,
)
from app.adapters.tdlib_json_client import (
    RealTdJsonClientFactory,
    TdlibClient,
    TdlibClientFactory,
    UnavailableTdlibClientFactory,
)
from app.config import Settings, settings
from app.logging_utils import log_event
from app.models import AccountState
from app.services.tdlib_proxy import apply_account_proxy_to_tdlib
from app.storage.paths import resolve_tdlib_account_dirs

RealTdJsonClient = _tdlib_json_client.RealTdJsonClient


@dataclass(frozen=True)
class _AuthOperationInput:
    account_id: str
    phone_number: str | None
    code: str | None
    password: str | None


@dataclass(frozen=True)
class _AuthOperationState:
    client: "TdlibClient"
    proxy_applied: bool = False
    recreated_after_closed: bool = False
    result: TdlibAuthResult | None = None


def search_chat_messages(
    client: TdlibClient,
    *,
    chat_id: int,
    random_id: int | None = None,
    limit: int = 10,
    timeout_seconds: float = 10.0,
) -> list[JsonDict]:
    """Fetch recent chat history and optionally filter messages by TDLib random_id."""
    fetch_limit = 50 if random_id is not None else max(1, limit)
    response = client.send_query(
        {
            "@type": "getChatHistory",
            "chat_id": chat_id,
            "from_message_id": 0,
            "offset": 0,
            "limit": fetch_limit,
            "only_local": False,
        },
        timeout_seconds,
    )
    if response.get("@type") == "error":
        raise RuntimeError(str(response.get("message") or "TDLib query failed"))

    raw_messages = response.get("messages")
    messages: list[JsonDict] = []
    if isinstance(raw_messages, list):
        for raw_message in cast(list[Any], raw_messages):
            if isinstance(raw_message, dict):
                messages.append(cast(JsonDict, raw_message))
    if random_id is not None:
        messages = [message for message in messages if message.get("random_id") == random_id]
    return messages[: max(1, limit)]


class TdlibAuthAdapter:
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

    def start_otp(self, account_id: str, phone_number: str) -> TdlibAuthResult:
        return self._run_auth_operation(
            account_id,
            phone_number=phone_number,
            code=None,
            password=None,
        )

    def confirm_otp(self, account_id: str, code: str) -> TdlibAuthResult:
        return self._run_auth_operation(
            account_id,
            phone_number=None,
            code=code,
            password=None,
        )

    def submit_password(self, account_id: str, password: str) -> TdlibAuthResult:
        return self._run_auth_operation(
            account_id,
            phone_number=None,
            code=None,
            password=password,
        )

    def _run_auth_operation(
        self,
        account_id: str,
        *,
        phone_number: str | None,
        code: str | None,
        password: str | None,
    ) -> TdlibAuthResult:
        auth_input = _AuthOperationInput(account_id, phone_number, code, password)
        if not self._config.tdlib_api_id or not self._config.tdlib_api_hash:
            return missing_tdlib_credentials_result()

        client: TdlibClient | None = None
        deadline = time.monotonic() + self._config.tdlib_auth_timeout_seconds
        try:
            client = self._client_factory.create(account_id)
            self._log_session_reused(account_id)
            state = _AuthOperationState(client=client)
            while time.monotonic() < deadline:
                event = _receive_client_event(
                    state.client, self._config.tdlib_receive_timeout_seconds
                )
                state = self._handle_auth_event(state, event, auth_input)
                client = state.client
                if state.result is not None:
                    return state.result
        except Exception as exc:
            return broken_tdlib_runtime_result(exc)
        finally:
            if client is not None:
                client.close()

        return tdlib_auth_timeout_result()

    def _log_session_reused(self, account_id: str) -> None:
        account_dirs = resolve_tdlib_account_dirs(self._config, account_id)
        log_event(
            "tdlib_session_reused",
            account_id=account_id,
            database_directory=str(account_dirs.database_directory),
            files_directory=str(account_dirs.files_directory),
        )

    def _handle_auth_event(
        self,
        state: _AuthOperationState,
        event: JsonDict | None,
        auth_input: _AuthOperationInput,
    ) -> _AuthOperationState:
        if event and event.get("@type") == "error":
            return _auth_state_result(state, map_tdlib_error(event))
        auth_state = _extract_authorization_state(event)
        if auth_state is None:
            return state

        mapped = map_authorization_state(auth_state)
        if mapped.status == TdlibAuthStatus.WAIT_TDLIB_PARAMETERS:
            return self._send_tdlib_parameters(state, auth_input.account_id)
        if _send_auth_input(state.client, mapped.status, auth_input):
            return state
        if mapped.status == TdlibAuthStatus.READY:
            return _auth_state_result(state, _ready_tdlib_auth_result(state.client, self._config))
        if mapped.status == TdlibAuthStatus.CLOSED and not state.recreated_after_closed:
            state.client.close()
            return _AuthOperationState(
                client=self._client_factory.create(auth_input.account_id),
                proxy_applied=state.proxy_applied,
                recreated_after_closed=True,
            )
        return _auth_state_result(state, mapped)

    def _send_tdlib_parameters(
        self, state: _AuthOperationState, account_id: str
    ) -> _AuthOperationState:
        state.client.send(_tdlib_parameters_query(self._config, account_id))
        proxy_applied = state.proxy_applied
        if self._proxy_applier is not None and not proxy_applied:
            proxy_applied = self._proxy_applier(state.client, account_id)
        return _AuthOperationState(
            client=state.client,
            proxy_applied=proxy_applied,
            recreated_after_closed=state.recreated_after_closed,
        )


def _auth_state_result(state: _AuthOperationState, result: TdlibAuthResult) -> _AuthOperationState:
    return _AuthOperationState(
        client=state.client,
        proxy_applied=state.proxy_applied,
        recreated_after_closed=state.recreated_after_closed,
        result=result,
    )


def _ready_tdlib_auth_result(client: TdlibClient, config: Settings) -> TdlibAuthResult:
    return TdlibAuthResult(
        status=TdlibAuthStatus.READY,
        account_state=AccountState.AUTHORIZED_READY,
        runtime_health="ready",
        needs_code=False,
        session_present=True,
        telegram_user_id=_get_current_user_id(client, config),
        recovery_marker="tdlib_ready",
    )


def _send_auth_input(
    client: TdlibClient, status: TdlibAuthStatus, auth_input: _AuthOperationInput
) -> bool:
    if status == TdlibAuthStatus.WAIT_PHONE_NUMBER and auth_input.phone_number:
        client.send(
            {
                "@type": "setAuthenticationPhoneNumber",
                "phone_number": auth_input.phone_number,
                "settings": None,
            }
        )
        return True
    if status == TdlibAuthStatus.WAIT_CODE and auth_input.code:
        client.send({"@type": "checkAuthenticationCode", "code": auth_input.code})
        return True
    if status == TdlibAuthStatus.WAIT_PASSWORD and auth_input.password:
        client.send({"@type": "checkAuthenticationPassword", "password": auth_input.password})
        return True
    return False


def normalize_phone_number(phone_number: str) -> str:
    stripped = phone_number.strip()
    if not stripped.startswith("+"):
        raise ValueError("phone number must be in international format")
    normalized = "+" + re.sub(r"\D", "", stripped)
    if not re.fullmatch(r"\+[1-9]\d{7,14}", normalized):
        raise ValueError("phone number must be in international format")
    return normalized


def build_tdlib_auth_adapter(config: Settings = settings) -> TdlibAuthAdapter:
    if not config.tdlib_api_id or not config.tdlib_api_hash:
        return TdlibAuthAdapter(
            client_factory=UnavailableTdlibClientFactory("TDLib credentials are not configured"),
            config=config,
            proxy_applier=lambda client, account_id: apply_account_proxy_to_tdlib(
                client, account_id, config=config
            ),
        )
    try:
        client_factory: TdlibClientFactory = RealTdJsonClientFactory(
            config.tdlib_shared_library_path
        )
    except OSError as exc:
        client_factory = UnavailableTdlibClientFactory(str(exc))
    return TdlibAuthAdapter(
        client_factory=client_factory,
        config=config,
        proxy_applier=lambda client, account_id: apply_account_proxy_to_tdlib(
            client, account_id, config=config
        ),
    )


def _extract_authorization_state(event: JsonDict | None) -> JsonDict | None:
    if not event:
        return None
    if event.get("@type") == "updateAuthorizationState":
        state = event.get("authorization_state")
        return cast(JsonDict, state) if isinstance(state, dict) else None
    if event.get("@type", "").startswith("authorizationState"):
        return event
    return None


def _receive_client_event(client: TdlibClient, timeout_seconds: float) -> JsonDict | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        remaining = max(deadline - time.monotonic(), 0.0)
        event = client.receive(remaining)
        if event is None:
            return None
        event_client_id = event.get("@client_id")
        if event_client_id is None or event_client_id == client.client_id:
            return event
    return None


def _tdlib_parameters_query(config: Settings, account_id: str) -> JsonDict:
    dirs = resolve_tdlib_account_dirs(config, account_id)
    return {
        "@type": "setTdlibParameters",
        "use_test_dc": config.tdlib_use_test_dc,
        "database_directory": str(dirs.database_directory),
        "files_directory": str(dirs.files_directory),
        "database_encryption_key": "",
        "use_file_database": True,
        "use_chat_info_database": False,
        "use_message_database": False,
        "use_secret_chats": False,
        "api_id": config.tdlib_api_id,
        "api_hash": config.tdlib_api_hash,
        "system_language_code": "en",
        "device_model": "StylistTG Backend",
        "system_version": "Windows",
        "application_version": "0.1.0",
    }


def _get_current_user_id(client: TdlibClient, config: Settings) -> str | None:
    try:
        user = client.send_query({"@type": "getMe"}, config.tdlib_receive_timeout_seconds)
    except Exception:
        return None
    user_id = user.get("id")
    return str(user_id) if user_id is not None else None


extract_authorization_state = _extract_authorization_state
tdlib_parameters_query = _tdlib_parameters_query
get_current_user_id = _get_current_user_id
