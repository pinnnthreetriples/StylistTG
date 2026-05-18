from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, cast

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
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        result: dict[object, Any] = {}
        for key, item in mapping.items():
            result[key] = "***" if is_sensitive_key(key) else redact_metadata(item)
        return result
    if isinstance(value, list):
        items = cast(list[object], value)
        return [redact_metadata(item) for item in items]
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_text(value: str) -> str:
    return _redact_url_credentials(_redact_key_values(value))


def _redact_key_values(text: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(text):
        quoted = _redact_quoted_key_value_at(text, index)
        if quoted is not None:
            replacement, index = quoted
            result.append(replacement)
            continue

        unquoted = _redact_unquoted_key_value_at(text, index)
        if unquoted is not None:
            replacement, index = unquoted
            result.append(replacement)
            continue

        result.append(text[index])
        index += 1
    return "".join(result)


def _redact_quoted_key_value_at(text: str, index: int) -> tuple[str, int] | None:
    quote = text[index]
    if quote not in {"'", '"'}:
        return None
    key_end = text.find(quote, index + 1)
    if key_end == -1:
        return None
    key = text[index + 1 : key_end]
    if not is_sensitive_key(key):
        return None
    separator_index = _skip_spaces(text, key_end + 1)
    if separator_index >= len(text) or text[separator_index] != ":":
        return None
    value_start = _skip_spaces(text, separator_index + 1)
    if value_start >= len(text):
        return None
    redacted_value, value_end = _redacted_value(text, value_start)
    return text[index:value_start] + redacted_value, value_end


def _redact_unquoted_key_value_at(text: str, index: int) -> tuple[str, int] | None:
    if index > 0 and _is_key_char(text[index - 1]):
        return None
    if not _is_key_char(text[index]):
        return None
    key_end = index + 1
    while key_end < len(text) and _is_key_char(text[key_end]):
        key_end += 1
    key = text[index:key_end]
    if not is_sensitive_key(key):
        return None
    separator_index = _skip_spaces(text, key_end)
    if separator_index >= len(text) or text[separator_index] not in {"=", ":"}:
        return None
    value_start = _skip_spaces(text, separator_index + 1)
    if value_start >= len(text):
        return None
    redacted_value, value_end = _redacted_value(text, value_start)
    return text[index:value_start] + redacted_value, value_end


def _redacted_value(text: str, value_start: int) -> tuple[str, int]:
    quote = text[value_start]
    if quote in {"'", '"'}:
        value_end = value_start + 1
        escaped = False
        while value_end < len(text):
            current = text[value_end]
            if current == quote and not escaped:
                return f"{quote}***{quote}", value_end + 1
            escaped = current == "\\" and not escaped
            if current != "\\":
                escaped = False
            value_end += 1
        return f"{quote}***", value_end

    value_end = value_start
    while value_end < len(text) and text[value_end] not in {" ", "\t", "\r", "\n", ",", ";"}:
        value_end += 1
    return "***", value_end


def _redact_url_credentials(text: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(text):
        scheme_end = text.find("://", index)
        if scheme_end == -1:
            result.append(text[index:])
            break
        result.append(text[index : scheme_end + 3])
        credential_start = scheme_end + 3
        segment_end = credential_start
        while segment_end < len(text) and not text[segment_end].isspace():
            segment_end += 1
        segment = text[credential_start:segment_end]
        at_index = segment.find("@")
        colon_index = segment.find(":")
        if 0 <= colon_index < at_index:
            result.append("***:***")
            result.append(segment[at_index:])
        else:
            result.append(segment)
        index = segment_end
    return "".join(result)


def _skip_spaces(text: str, index: int) -> int:
    while index < len(text) and text[index] in {" ", "\t", "\r", "\n"}:
        index += 1
    return index


def _is_key_char(value: str) -> bool:
    return value.isalnum() or value == "_"


def is_sensitive_key(key: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return any(fragment.replace("_", "") in normalized for fragment in SENSITIVE_FRAGMENTS)
