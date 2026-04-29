from __future__ import annotations

import re

from app.models import AuthBatchItem, AuthBatchItemStatus


def parse_flood_wait_seconds(message: str | None) -> int:
    if not message:
        return 60
    match = re.search(r"FLOOD_WAIT_?(\d+)", message.upper())
    return int(match.group(1)) if match else 60


def apply_auth_error(item: AuthBatchItem, message: str | None) -> str:
    upper = (message or "TDLib error").upper()
    item.error_message = message or "TDLib error"
    if "PHONE_CODE_INVALID" in upper:
        item.code_error_count += 1
        item.error_code = "PHONE_CODE_INVALID"
        return AuthBatchItemStatus.FAILED if item.code_error_count >= 3 else AuthBatchItemStatus.WAITING_CODE
    if "PHONE_CODE_EXPIRED" in upper:
        item.error_code = "PHONE_CODE_EXPIRED"
        return AuthBatchItemStatus.TIMED_OUT
    if "PASSWORD_HASH_INVALID" in upper:
        item.password_error_count += 1
        item.error_code = "PASSWORD_HASH_INVALID"
        return AuthBatchItemStatus.FAILED if item.password_error_count >= 5 else AuthBatchItemStatus.WAITING_2FA
    if "PHONE_NUMBER_BANNED" in upper:
        item.error_code = "PHONE_NUMBER_BANNED"
        return AuthBatchItemStatus.FAILED
    if "PHONE_NUMBER_INVALID" in upper:
        item.error_code = "PHONE_NUMBER_INVALID"
        return AuthBatchItemStatus.FAILED
    if "FLOOD" in upper:
        item.error_code = "FLOOD_WAIT"
        return AuthBatchItemStatus.QUEUED
    item.error_code = "TDLIB_AUTH_ERROR"
    return AuthBatchItemStatus.FAILED
