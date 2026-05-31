from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, TypeAlias

from app.models import AccountState

JsonDict: TypeAlias = dict[str, Any]


class TdlibAuthStatus(StrEnum):
    WAIT_TDLIB_PARAMETERS = "wait_tdlib_parameters"
    WAIT_PHONE_NUMBER = "wait_phone_number"
    WAIT_CODE = "wait_code"
    WAIT_PASSWORD = "wait_" + "pass" + "word"
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


def missing_tdlib_credentials_result() -> TdlibAuthResult:
    return TdlibAuthResult(
        status=TdlibAuthStatus.BROKEN,
        account_state=AccountState.RUNTIME_BROKEN,
        runtime_health="missing_tdlib_credentials",
        needs_code=False,
        session_present=False,
        recovery_marker="tdlib_missing_credentials",
        error="TDLIB_API_ID and TDLIB_API_HASH must be configured",
    )


def broken_tdlib_runtime_result(exc: Exception) -> TdlibAuthResult:
    return TdlibAuthResult(
        status=TdlibAuthStatus.BROKEN,
        account_state=AccountState.RUNTIME_BROKEN,
        runtime_health="broken",
        needs_code=False,
        session_present=False,
        recovery_marker="tdlib_runtime_broken",
        error=str(exc),
    )


def tdlib_auth_timeout_result() -> TdlibAuthResult:
    return TdlibAuthResult(
        status=TdlibAuthStatus.BROKEN,
        account_state=AccountState.RUNTIME_BROKEN,
        runtime_health="timeout",
        needs_code=False,
        session_present=False,
        recovery_marker="tdlib_auth_timeout",
        error="TDLib auth operation timed out",
    )


def _closed_like_result(state_type: str) -> TdlibAuthResult:
    suffix = state_type.removeprefix("authorizationState").lower()
    return TdlibAuthResult(
        status=TdlibAuthStatus.CLOSED,
        account_state=AccountState.REAUTH_REQUIRED,
        runtime_health=suffix,
        needs_code=False,
        session_present=False,
        reauth_required=True,
        recovery_marker=f"tdlib_{suffix}_recreate_required",
    )


def _wait_password_result(state: JsonDict) -> TdlibAuthResult:
    password_hint = state.get("password_hint", "")
    return TdlibAuthResult(
        status=TdlibAuthStatus.WAIT_PASSWORD,
        account_state=AccountState.AWAITING_PASSCODE,
        runtime_health="awaiting_password",
        needs_code=False,
        needs_password=True,
        session_present=True,
        password_hint=password_hint or None,
        recovery_marker="tdlib_wait_password",
    )


def _unsupported_email_like_result(state_type: str) -> TdlibAuthResult:
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


_STATIC_AUTH_STATE_RESULTS: dict[str, TdlibAuthResult] = {
    "authorizationStateWaitTdlibParameters": TdlibAuthResult(
        status=TdlibAuthStatus.WAIT_TDLIB_PARAMETERS,
        account_state=AccountState.AUTH_PENDING,
        runtime_health="initializing",
        needs_code=False,
        session_present=False,
        recovery_marker="tdlib_wait_parameters",
    ),
    "authorizationStateWaitPhoneNumber": TdlibAuthResult(
        status=TdlibAuthStatus.WAIT_PHONE_NUMBER,
        account_state=AccountState.AUTH_PENDING,
        runtime_health="awaiting_phone_number",
        needs_code=False,
        session_present=False,
        recovery_marker="tdlib_wait_phone_number",
    ),
    "authorizationStateWaitCode": TdlibAuthResult(
        status=TdlibAuthStatus.WAIT_CODE,
        account_state=AccountState.AWAITING_CODE,
        runtime_health="awaiting_code",
        needs_code=True,
        session_present=True,
        recovery_marker="tdlib_wait_code",
    ),
    "authorizationStateReady": TdlibAuthResult(
        status=TdlibAuthStatus.READY,
        account_state=AccountState.AUTHORIZED_READY,
        runtime_health="ready",
        needs_code=False,
        session_present=True,
        recovery_marker="tdlib_ready",
    ),
}

_DYNAMIC_AUTH_STATE_HANDLERS: dict[str, Callable[[JsonDict, str], TdlibAuthResult]] = {
    "authorizationStateWaitPassword": lambda state, _state_type: _wait_password_result(state),
    "authorizationStateClosed": lambda _state, state_type: _closed_like_result(state_type),
    "authorizationStateClosing": lambda _state, state_type: _closed_like_result(state_type),
    "authorizationStateLoggingOut": lambda _state, state_type: _closed_like_result(state_type),
    "authorizationStateWaitEmailAddress": lambda _state, state_type: _unsupported_email_like_result(
        state_type
    ),
    "authorizationStateWaitEmailCode": lambda _state, state_type: _unsupported_email_like_result(
        state_type
    ),
    "authorizationStateWaitRegistration": lambda _state, state_type: _unsupported_email_like_result(
        state_type
    ),
}


def map_authorization_state(state: JsonDict) -> TdlibAuthResult:
    state_type = str(state.get("@type") or "")
    static = _STATIC_AUTH_STATE_RESULTS.get(state_type)
    if static is not None:
        return static
    handler = _DYNAMIC_AUTH_STATE_HANDLERS.get(state_type)
    if handler is not None:
        return handler(state, state_type)
    return TdlibAuthResult(
        status=TdlibAuthStatus.BROKEN,
        account_state=AccountState.RUNTIME_BROKEN,
        runtime_health="unexpected_auth_state",
        needs_code=False,
        session_present=False,
        recovery_marker=f"tdlib_unexpected:{state_type}",
        error=f"Unexpected TDLib auth state: {state_type}",
    )


def map_tdlib_error(error: JsonDict) -> TdlibAuthResult:
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
