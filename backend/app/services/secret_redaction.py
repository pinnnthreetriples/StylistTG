from __future__ import annotations

import re
from typing import Any

SENSITIVE_FRAGMENTS = (
    "password",
    "proxy_password",
    "token",
    "jwt",
    "secret",
    "api_hash",
    "apihash",
    "operator_api_token",
    "auth_code",
    "authcode",
    "two_factor_password",
    "twofactorpassword",
)


def redact_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            result[key] = "***" if is_sensitive_key(key) else redact_metadata(item)
        return result
    if isinstance(value, list):
        return [redact_metadata(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_text(value: str) -> str:
    text = value
    key_pattern = (
        r"(?:password|proxy_password|token|jwt|secret|api_hash|apihash|"
        r"operator_api_token|auth_code|authcode|two_factor_password|twofactorpassword)"
    )
    text = re.sub(
        rf"(?i)([\"'](?:{key_pattern})[\"']\s*:\s*)([\"']).*?\2",
        r"\1\2***\2",
        text,
    )
    text = re.sub(rf"(?i)\b({key_pattern})\b(\s*=\s*)[^\s,;]+", r"\1\2***", text)
    text = re.sub(rf"(?i)\b({key_pattern})\b(\s*:\s*)[^\s,;]+", r"\1\2***", text)
    text = re.sub(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^:/@\s]+):([^@\s]+)@", r"\1***:***@", text)
    return text


def is_sensitive_key(key: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return any(fragment.replace("_", "") in normalized for fragment in SENSITIVE_FRAGMENTS)
