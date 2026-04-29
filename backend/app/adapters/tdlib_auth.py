from __future__ import annotations

import ctypes
import json
import re
import time
import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from app.config import Settings, settings
from app.logging_utils import log_event
from app.models import AccountState


class TdlibAuthStatus(StrEnum):
    WAIT_TDLIB_PARAMETERS = "wait_tdlib_parameters"
    WAIT_PHONE_NUMBER = "wait_phone_number"
    WAIT_CODE = "wait_code"
    WAIT_PASSWORD = "wait_password"
    READY = "ready"
    CLOSED = "closed"
    UNSUPPORTED = "unsupported"
    BROKEN = "broken"


@dataclass(frozen=True)
class TdlibAuthResult:
    status: TdlibAuthStatus
    account_state: AccountState
    runtime_health: str
    needs_code: bool
    session_present: bool
    reauth_required: bool = False
    needs_password: bool = False
    needs_manual_intervention: bool = False
    telegram_user_id: str | None = None
    password_hint: str | None = None
    recovery_marker: str | None = None
    error: str | None = None


class TdlibClient(Protocol):
    @property
    def client_id(self) -> int: ...

    def send(self, query: dict) -> None: ...

    def receive(self, timeout_seconds: float) -> dict | None: ...

    def send_query(self, query: dict, timeout_seconds: float) -> dict: ...

    def close(self) -> None: ...


class TdlibClientFactory(Protocol):
    def create(self, account_id: str) -> TdlibClient: ...


class RealTdJsonClient:
    def __init__(self, library: ctypes.CDLL) -> None:
        self._library = library
        self._client = library.td_json_client_create()
        self._closed = False
        self._pending_events: list[dict] = []

    @property
    def client_id(self) -> int:
        return 0

    def send(self, query: dict) -> None:
        self._library.td_json_client_send(
            self._client, json.dumps(query).encode("utf-8")
        )

    def receive(self, timeout_seconds: float) -> dict | None:
        if self._pending_events:
            return self._pending_events.pop(0)
        return self._receive_raw(timeout_seconds)

    def _receive_raw(self, timeout_seconds: float) -> dict | None:
        raw = self._library.td_json_client_receive(self._client, timeout_seconds)
        if not raw:
            return None
        return json.loads(ctypes.cast(raw, ctypes.c_char_p).value.decode("utf-8"))

    def send_query(self, query: dict, timeout_seconds: float) -> dict:
        extra = str(uuid.uuid4())
        self.send({**query, "@extra": extra})
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            response = self._receive_raw(1.0)
            if not response:
                continue
            if response.get("@extra") == extra:
                return response
            self._pending_events.append(response)
        raise TimeoutError(f"TDLib query timed out: {query.get('@type')}")

    def close(self) -> None:
        if not self._closed:
            self._library.td_json_client_destroy(self._client)
            self._closed = True


class RealTdJsonClientFactory:
    def __init__(self, shared_library_path: Path | None = None) -> None:
        path = str(shared_library_path) if shared_library_path else _default_tdjson_library_name()
        self._library = ctypes.CDLL(path)
        self._library.td_json_client_create.restype = ctypes.c_void_p
        self._library.td_json_client_send.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self._library.td_json_client_receive.argtypes = [ctypes.c_void_p, ctypes.c_double]
        self._library.td_json_client_receive.restype = ctypes.c_char_p
        self._library.td_json_client_execute.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self._library.td_json_client_execute.restype = ctypes.c_char_p
        self._library.td_json_client_destroy.argtypes = [ctypes.c_void_p]

    def create(self, account_id: str) -> RealTdJsonClient:
        return RealTdJsonClient(self._library)


class UnavailableTdlibClientFactory:
    def __init__(self, reason: str) -> None:
        self._reason = reason

    def create(self, account_id: str) -> TdlibClient:
        raise RuntimeError(self._reason)


class TdlibAuthAdapter:
    def __init__(
        self,
        *,
        client_factory: TdlibClientFactory,
        config: Settings = settings,
    ) -> None:
        self._client_factory = client_factory
        self._config = config

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
        if not self._config.tdlib_api_id or not self._config.tdlib_api_hash:
            return TdlibAuthResult(
                status=TdlibAuthStatus.BROKEN,
                account_state=AccountState.RUNTIME_BROKEN,
                runtime_health="missing_tdlib_credentials",
                needs_code=False,
                session_present=False,
                recovery_marker="tdlib_missing_credentials",
                error="TDLIB_API_ID and TDLIB_API_HASH must be configured",
            )

        client = self._client_factory.create(account_id)
        log_event(
            "tdlib_session_reused",
            account_id=account_id,
            database_directory=str(self._config.tdlib_database_root / account_id),
            files_directory=str(self._config.tdlib_files_root / account_id),
        )
        recreated_after_closed = False
        deadline = time.monotonic() + self._config.tdlib_auth_timeout_seconds
        try:
            while time.monotonic() < deadline:
                event = _receive_client_event(
                    client, self._config.tdlib_receive_timeout_seconds
                )
                if event and event.get("@type") == "error":
                    return map_tdlib_error(event)
                auth_state = _extract_authorization_state(event)
                if auth_state is None:
                    continue

                mapped = map_authorization_state(auth_state)
                if mapped.status == TdlibAuthStatus.WAIT_TDLIB_PARAMETERS:
                    client.send(_tdlib_parameters_query(self._config, account_id))
                    continue
                if mapped.status == TdlibAuthStatus.WAIT_PHONE_NUMBER and phone_number:
                    client.send(
                        {
                            "@type": "setAuthenticationPhoneNumber",
                            "phone_number": phone_number,
                            "settings": None,
                        }
                    )
                    continue
                if mapped.status == TdlibAuthStatus.WAIT_CODE and code:
                    client.send({"@type": "checkAuthenticationCode", "code": code})
                    continue
                if mapped.status == TdlibAuthStatus.WAIT_PASSWORD and password:
                    client.send({"@type": "checkAuthenticationPassword", "password": password})
                    continue
                if mapped.status == TdlibAuthStatus.READY:
                    telegram_user_id = _get_current_user_id(client, self._config)
                    return TdlibAuthResult(
                        status=TdlibAuthStatus.READY,
                        account_state=AccountState.AUTHORIZED_READY,
                        runtime_health="ready",
                        needs_code=False,
                        session_present=True,
                        telegram_user_id=telegram_user_id,
                        recovery_marker="tdlib_ready",
                    )
                if mapped.status == TdlibAuthStatus.CLOSED and not recreated_after_closed:
                    client.close()
                    client = self._client_factory.create(account_id)
                    recreated_after_closed = True
                    continue
                return mapped
        except Exception as exc:
            return TdlibAuthResult(
                status=TdlibAuthStatus.BROKEN,
                account_state=AccountState.RUNTIME_BROKEN,
                runtime_health="broken",
                needs_code=False,
                session_present=False,
                recovery_marker="tdlib_runtime_broken",
                error=str(exc),
            )
        finally:
            client.close()

        return TdlibAuthResult(
            status=TdlibAuthStatus.BROKEN,
            account_state=AccountState.RUNTIME_BROKEN,
            runtime_health="timeout",
            needs_code=False,
            session_present=False,
            recovery_marker="tdlib_auth_timeout",
            error="TDLib auth operation timed out",
        )


def normalize_phone_number(phone_number: str) -> str:
    stripped = phone_number.strip()
    if not stripped.startswith("+"):
        raise ValueError("phone number must be in international format")
    normalized = "+" + re.sub(r"\D", "", stripped)
    if not re.fullmatch(r"\+[1-9]\d{7,14}", normalized):
        raise ValueError("phone number must be in international format")
    return normalized


def map_authorization_state(state: dict) -> TdlibAuthResult:
    state_type = state.get("@type")
    if state_type == "authorizationStateWaitTdlibParameters":
        return TdlibAuthResult(
            status=TdlibAuthStatus.WAIT_TDLIB_PARAMETERS,
            account_state=AccountState.AUTH_PENDING,
            runtime_health="initializing",
            needs_code=False,
            session_present=False,
            recovery_marker="tdlib_wait_parameters",
        )
    if state_type == "authorizationStateWaitPhoneNumber":
        return TdlibAuthResult(
            status=TdlibAuthStatus.WAIT_PHONE_NUMBER,
            account_state=AccountState.AUTH_PENDING,
            runtime_health="awaiting_phone_number",
            needs_code=False,
            session_present=False,
            recovery_marker="tdlib_wait_phone_number",
        )
    if state_type == "authorizationStateWaitCode":
        return TdlibAuthResult(
            status=TdlibAuthStatus.WAIT_CODE,
            account_state=AccountState.AWAITING_CODE,
            runtime_health="awaiting_code",
            needs_code=True,
            session_present=True,
            recovery_marker="tdlib_wait_code",
        )
    if state_type == "authorizationStateReady":
        return TdlibAuthResult(
            status=TdlibAuthStatus.READY,
            account_state=AccountState.AUTHORIZED_READY,
            runtime_health="ready",
            needs_code=False,
            session_present=True,
            recovery_marker="tdlib_ready",
        )
    if state_type in {
        "authorizationStateClosed",
        "authorizationStateClosing",
        "authorizationStateLoggingOut",
    }:
        return TdlibAuthResult(
            status=TdlibAuthStatus.CLOSED,
            account_state=AccountState.REAUTH_REQUIRED,
            runtime_health=state_type.removeprefix("authorizationState").lower(),
            needs_code=False,
            session_present=False,
            reauth_required=True,
            recovery_marker=f"tdlib_{state_type.removeprefix('authorizationState').lower()}_recreate_required",
        )
    if state_type == "authorizationStateWaitPassword":
        password_hint = state.get("password_hint", "")
        return TdlibAuthResult(
            status=TdlibAuthStatus.WAIT_PASSWORD,
            account_state=AccountState.AWAITING_PASSWORD,
            runtime_health="awaiting_password",
            needs_code=False,
            needs_password=True,
            session_present=True,
            password_hint=password_hint or None,
            recovery_marker="tdlib_wait_password",
        )
    if state_type in {
        "authorizationStateWaitEmailAddress",
        "authorizationStateWaitEmailCode",
        "authorizationStateWaitRegistration",
    }:
        return TdlibAuthResult(
            status=TdlibAuthStatus.UNSUPPORTED,
            account_state=AccountState.MANUAL_INTERVENTION_NEEDED,
            runtime_health=state_type.removeprefix("authorizationState"),
            needs_code=False,
            session_present=True,
            needs_manual_intervention=True,
            recovery_marker=f"tdlib_unsupported:{state_type}",
            error=f"Unsupported TDLib auth branch: {state_type}",
        )
    return TdlibAuthResult(
        status=TdlibAuthStatus.BROKEN,
        account_state=AccountState.RUNTIME_BROKEN,
        runtime_health="unexpected_auth_state",
        needs_code=False,
        session_present=False,
        recovery_marker=f"tdlib_unexpected:{state_type}",
        error=f"Unexpected TDLib auth state: {state_type}",
    )


def map_tdlib_error(error: dict) -> TdlibAuthResult:
    message = str(error.get("message") or "TDLib error")
    upper_message = message.upper()
    if "FROZEN" in upper_message:
        return TdlibAuthResult(
            status=TdlibAuthStatus.UNSUPPORTED,
            account_state=AccountState.MANUAL_INTERVENTION_NEEDED,
            runtime_health="frozen",
            needs_code=False,
            session_present=True,
            reauth_required=True,
            needs_manual_intervention=True,
            recovery_marker=f"tdlib_hard_stop:{upper_message}",
            error=message,
        )
    if "FLOOD" in upper_message:
        return TdlibAuthResult(
            status=TdlibAuthStatus.UNSUPPORTED,
            account_state=AccountState.MANUAL_INTERVENTION_NEEDED,
            runtime_health="flood",
            needs_code=False,
            session_present=True,
            reauth_required=True,
            needs_manual_intervention=True,
            recovery_marker=f"tdlib_hard_stop:{upper_message}",
            error=message,
        )
    return TdlibAuthResult(
        status=TdlibAuthStatus.BROKEN,
        account_state=AccountState.RUNTIME_BROKEN,
        runtime_health="tdlib_error",
        needs_code=False,
        session_present=False,
        recovery_marker="tdlib_error",
        error=message,
    )


def build_tdlib_auth_adapter(config: Settings = settings) -> TdlibAuthAdapter:
    if not config.tdlib_api_id or not config.tdlib_api_hash:
        return TdlibAuthAdapter(
            client_factory=UnavailableTdlibClientFactory("TDLib credentials are not configured"),
            config=config,
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
    )


def _extract_authorization_state(event: dict | None) -> dict | None:
    if not event:
        return None
    if event.get("@type") == "updateAuthorizationState":
        return event.get("authorization_state")
    if event.get("@type", "").startswith("authorizationState"):
        return event
    return None


def _receive_client_event(
    client: TdlibClient, timeout_seconds: float
) -> dict | None:
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


def _tdlib_parameters_query(config: Settings, account_id: str) -> dict:
    database_directory = config.tdlib_database_root / account_id
    files_directory = config.tdlib_files_root / account_id
    database_directory.mkdir(parents=True, exist_ok=True)
    files_directory.mkdir(parents=True, exist_ok=True)
    return {
        "@type": "setTdlibParameters",
        "use_test_dc": config.tdlib_use_test_dc,
        "database_directory": str(database_directory),
        "files_directory": str(files_directory),
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


def _default_tdjson_library_name() -> str:
    return "tdjson.dll"
