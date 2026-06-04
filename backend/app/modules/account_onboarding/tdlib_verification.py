from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.adapters.tdlib_readonly_validity import build_tdlib_readonly_validity_adapter


@dataclass(frozen=True, slots=True)
class TdlibImportVerification:
    outcome: str
    telegram_user_id: str | None = None
    error_code: str | None = None
    message: str | None = None
    profile: dict[str, Any] | None = None


def verify_imported_tdlib_session(
    account_id: str, *, expected_telegram_user_id: str | None = None
) -> TdlibImportVerification:
    raw = build_tdlib_readonly_validity_adapter().check_account(account_id)
    status = str(raw.get("status") or "unknown")
    runtime_health = str(raw.get("runtime_health") or "")
    error_code = str(raw.get("error_code") or "") or None
    telegram_user_id = raw.get("telegram_user_id")
    telegram_user_id = str(telegram_user_id) if telegram_user_id is not None else None
    if status == "valid":
        if expected_telegram_user_id and telegram_user_id != expected_telegram_user_id:
            return TdlibImportVerification(
                outcome="identity_mismatch",
                telegram_user_id=telegram_user_id,
                error_code="tdlib_identity_mismatch",
                message="Verified Telegram identity does not match expected account.",
            )
        return TdlibImportVerification(
            outcome="verified_ready",
            telegram_user_id=telegram_user_id,
            profile=raw.get("profile") if isinstance(raw.get("profile"), dict) else None,
        )
    if status == "reauth_required":
        return TdlibImportVerification(
            outcome="requires_reauth",
            error_code=error_code or "tdlib_import_requires_reauth",
            message="Readonly TDLib verification requires reauth.",
        )
    if error_code == "missing_tdlib_credentials":
        return TdlibImportVerification(
            outcome="tdlib_not_configured",
            error_code=error_code,
            message="TDLib credentials are not configured.",
        )
    if runtime_health == "timeout" or error_code == "tdlib_readonly_timeout":
        return TdlibImportVerification(
            outcome="verification_timeout",
            error_code=error_code or "tdlib_readonly_timeout",
            message="Readonly TDLib verification timed out.",
        )
    if status == "runtime_broken":
        return TdlibImportVerification(
            outcome="tdlib_unavailable",
            error_code=error_code or "tdlib_readonly_runtime_broken",
            message="Readonly TDLib runtime is unavailable.",
        )
    return TdlibImportVerification(
        outcome="verification_failed",
        error_code=error_code or "tdlib_import_verification_failed",
        message="Readonly TDLib verification did not produce a ready session.",
    )
