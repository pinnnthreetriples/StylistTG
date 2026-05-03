from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.services.tdlib_client import TdlibJsonClient, safe_tdlib_error_message


AUTH_ERROR_MAP = {
    "PHONE_NUMBER_INVALID": "phone_number_invalid",
    "PHONE_CODE_INVALID": "code_invalid",
    "PHONE_CODE_EXPIRED": "code_expired",
    "PASSWORD_HASH_INVALID": "password_invalid",
}


@dataclass(frozen=True)
class TdlibAuthTransition:
    status: str
    requires_code: bool = False
    requires_password: bool = False
    error_code: str | None = None
    error_message: str | None = None
    me: dict[str, Any] | None = None
    flood_wait_seconds: int | None = None


class TdlibAuthStateMachine:
    def __init__(self, client: TdlibJsonClient) -> None:
        self.client = client

    def start(self, *, phone_number: str) -> TdlibAuthTransition:
        self.client.send({"@type": "setAuthenticationPhoneNumber", "phone_number": phone_number})
        return self._next_transition(default=TdlibAuthTransition(status="waiting_code", requires_code=True))

    def submit_code(self, *, code: str) -> TdlibAuthTransition:
        self.client.send({"@type": "checkAuthenticationCode", "code": code})
        return self._next_transition(default=TdlibAuthTransition(status="waiting_password", requires_password=True))

    def submit_password(self, *, password: str) -> TdlibAuthTransition:
        self.client.send({"@type": "checkAuthenticationPassword", "password": password})
        self.client.send({"@type": "getMe"})
        return self._next_transition(default=TdlibAuthTransition(status="ready", me={"id": "unknown"}))

    def cancel(self) -> TdlibAuthTransition:
        self.client.send({"@type": "close"})
        self.client.close()
        return TdlibAuthTransition(status="canceled")

    def _next_transition(self, *, default: TdlibAuthTransition) -> TdlibAuthTransition:
        update = self.client.receive(0.1)
        if update is None:
            return default
        update_type = update.get("@type")
        if update_type == "error":
            return _error_transition(update)
        if update_type == "updateAuthorizationState":
            state = update.get("authorization_state") or {}
            return _auth_state_transition(state)
        if update_type == "user":
            return TdlibAuthTransition(status="ready", me=update)
        return default


def _auth_state_transition(state: dict[str, Any]) -> TdlibAuthTransition:
    state_type = state.get("@type")
    if state_type == "authorizationStateWaitCode":
        return TdlibAuthTransition(status="waiting_code", requires_code=True)
    if state_type == "authorizationStateWaitPassword":
        return TdlibAuthTransition(status="waiting_password", requires_password=True)
    if state_type == "authorizationStateReady":
        return TdlibAuthTransition(status="ready")
    if state_type in {"authorizationStateClosed", "authorizationStateClosing", "authorizationStateLoggingOut"}:
        return TdlibAuthTransition(status="canceled")
    if state_type == "authorizationStateWaitPhoneNumber":
        return TdlibAuthTransition(status="waiting_phone")
    return TdlibAuthTransition(status="queued")


def _error_transition(update: dict[str, Any]) -> TdlibAuthTransition:
    raw_message = safe_tdlib_error_message(update.get("message") or update.get("code") or "tdlib error")
    code = AUTH_ERROR_MAP.get(str(update.get("message")), "tdlib_runtime_error")
    flood_wait = _flood_wait_seconds(raw_message)
    if flood_wait is not None:
        code = "flood_wait"
    return TdlibAuthTransition(status="failed", error_code=code, error_message=raw_message, flood_wait_seconds=flood_wait)


def _flood_wait_seconds(message: str) -> int | None:
    match = re.search(r"FLOOD_WAIT[_ ](?P<seconds>\d+)", message.upper())
    if not match:
        return None
    return min(max(int(match.group("seconds")), 1), 86400)
