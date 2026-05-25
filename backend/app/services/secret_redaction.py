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

# Audit B F-001: PII key fragments. Detected the same way as SENSITIVE_FRAGMENTS
# (case-insensitive, separators stripped) but mapped to type-specific tokens so
# downstream readers can distinguish a redacted email from a redacted secret.
PII_EMAIL_KEY_FRAGMENTS = (
    "email",
    "contactemail",
    "owneremail",
    "useremail",
    "actoremail",
)

PII_PHONE_KEY_FRAGMENTS = (
    "phone",
    "phonenumber",
    "contactphone",
    "tgphone",
    "telephone",
    "mobile",
)

REDACTED_EMAIL = "[REDACTED_EMAIL]"
REDACTED_PHONE = "[REDACTED_PHONE]"

# Free-text PII patterns. Conservative: phones require at least 9 digits to
# avoid matching IDs/timestamps; bounded by non-word characters on both sides.
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\w)\+?\d[\d\s\-().]{7,18}\d(?!\w)")
_PHONE_MIN_DIGITS = 9
_PHONE_MAX_DIGITS = 16
# Real phone-segment groups are 1-5 digits; UUIDs (8-4-4-4-12) and other
# dash-separated opaque IDs always exceed this in at least one group.
_PHONE_GROUP_MAX_DIGITS = 5


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


def redact_pii(value: Any) -> Any:
    """Recursively redact emails, phones, and credentials.

    Supersedes :func:`redact_metadata` for any callsite that needs PII
    coverage (audit log metadata, structured logging kwargs). Three layers:

    1. **Key-based masking** — values for keys whose normalized form matches
       an email/phone fragment are replaced with ``[REDACTED_EMAIL]`` /
       ``[REDACTED_PHONE]``. Generic secret keys still mask with ``***``.
    2. **Pattern-based masking** — emails and phone-like substrings inside
       any string value are replaced with the same tokens.
    3. **Recursive nesting** — applies to dict/list/tuple containers.

    Non-string, non-container values pass through unchanged. Safe for
    arbitrary metadata payloads typical of sensitive audit events.
    """
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        result: dict[object, Any] = {}
        for key, item in mapping.items():
            normalized = _normalize_key(key)
            if any(fragment in normalized for fragment in PII_EMAIL_KEY_FRAGMENTS):
                result[key] = REDACTED_EMAIL
            elif any(fragment in normalized for fragment in PII_PHONE_KEY_FRAGMENTS):
                result[key] = REDACTED_PHONE
            elif is_sensitive_key(key):
                result[key] = "***"
            else:
                result[key] = redact_pii(item)
        return result
    if isinstance(value, (list, tuple)):
        sequence = cast("list[object] | tuple[object, ...]", value)
        return [redact_pii(item) for item in sequence]
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_text(value: str) -> str:
    return _redact_pii_patterns(_redact_url_credentials(_redact_key_values(value)))


def _redact_pii_patterns(text: str) -> str:
    """Apply free-text email/phone regex masking to ``text``."""
    text = _EMAIL_RE.sub(REDACTED_EMAIL, text)
    text = _PHONE_RE.sub(_phone_substitution, text)
    return text


def _phone_substitution(match: re.Match[str]) -> str:
    raw = match.group(0)
    digit_count = sum(1 for c in raw if c.isdigit())
    if not (_PHONE_MIN_DIGITS <= digit_count <= _PHONE_MAX_DIGITS):
        return raw
    # E.164-style leading + is unambiguous; mask outright.
    if raw.startswith("+"):
        return REDACTED_PHONE
    # Otherwise require a phone-shaped separator (space, dot, paren) OR
    # dash-separated digit groups that look like a phone number layout.
    # UUIDs (8-4-4-4-12) and opaque dash-separated IDs have at least one
    # group longer than 5 digits, which is unrealistic for any real-world
    # phone segment — that disqualifier is what keeps false positives down.
    if any(ch in raw for ch in " ()."):
        return REDACTED_PHONE
    groups = [g for g in raw.split("-") if g]
    if (
        len(groups) >= 3
        and all(g.isdigit() for g in groups)
        and all(1 <= len(g) <= _PHONE_GROUP_MAX_DIGITS for g in groups)
    ):
        return REDACTED_PHONE
    return raw


def _normalize_key(key: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


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
    normalized = _normalize_key(key)
    return any(fragment.replace("_", "") in normalized for fragment in SENSITIVE_FRAGMENTS)
