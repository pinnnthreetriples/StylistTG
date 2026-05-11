from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, cast

from app.config import settings
from app.services.secret_redaction import is_sensitive_key, redact_metadata, redact_text

BeforeSend = Callable[[dict[str, Any], Any], dict[str, Any] | None]

_initialized = False

TDJSON_LIBRARY_PATTERN = re.compile(
    r"(?i)(?:[A-Za-z]:)?(?:[/\\][^\s,;:\"']+)*[/\\]?(?:lib)?tdjson\.(?:dll|so|dylib)\b"
)

SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-operator-token",
    "x-supabase-auth",
}

SENSITIVE_FIELD_NAMES = {
    "authorization",
    "cookie",
    "database_url",
    "dsn",
    "jwt",
    "phone",
    "proxy",
    "redis_url",
    "request_body",
    "service_role",
    "session",
    "supabase",
    "tdlib",
    "telegram",
    "token",
}

SENSITIVE_EVENT_KEYS = {
    "request",
    "headers",
    "cookies",
    "query_string",
    "data",
    "body",
    "raw_body",
    "form",
    "json",
}


def init_api_observability() -> bool:
    dsn = (
        settings.better_stack_api_dsn.get_secret_value() if settings.better_stack_api_dsn else None
    )
    return _init_sentry(dsn=dsn, integrations=("fastapi",))


def init_worker_observability() -> bool:
    dsn = (
        settings.better_stack_worker_dsn.get_secret_value()
        if settings.better_stack_worker_dsn
        else None
    )
    return _init_sentry(dsn=dsn, integrations=("rq",))


def capture_observability_test_exception(message: str) -> bool:
    try:
        import sentry_sdk
    except ImportError:
        return False

    try:
        raise RuntimeError(message)
    except RuntimeError as exc:
        event_id = sentry_sdk.capture_exception(exc)
        sentry_sdk.flush(timeout=2.0)
        return event_id is not None


def sanitize_sentry_event(event: dict[str, Any], _hint: Any = None) -> dict[str, Any] | None:
    sanitized = _sanitize_value(event)
    return cast(dict[str, Any], sanitized) if isinstance(sanitized, dict) else None


def _init_sentry(*, dsn: str | None, integrations: tuple[str, ...]) -> bool:
    global _initialized
    if not dsn:
        return False
    if _initialized:
        return True

    try:
        import sentry_sdk
    except ImportError:
        return False

    try:
        sentry_integrations: list[Any] = []
        if "fastapi" in integrations:
            from sentry_sdk.integrations.fastapi import FastApiIntegration

            sentry_integrations.append(FastApiIntegration())
        if "rq" in integrations:
            from sentry_sdk.integrations.rq import RqIntegration

            sentry_integrations.append(RqIntegration())

        sentry_sdk.init(
            dsn=dsn,
            environment=settings.sentry_environment,
            release=settings.sentry_release,
            send_default_pii=False,
            traces_sample_rate=0.0,
            integrations=sentry_integrations,
            before_send=cast(Any, sanitize_sentry_event),
        )
    except Exception as exc:
        _log_observability_init_error(exc)
        return False
    _initialized = True
    return True


def _sanitize_value(value: Any, *, key: str | None = None, parent_key: str | None = None) -> Any:
    if key and _is_sensitive_event_key(key):
        return "***"
    if key and key.lower() in SENSITIVE_EVENT_KEYS:
        return _sanitize_sensitive_container(key, value, parent_key=parent_key)
    if isinstance(value, dict):
        typed_value = cast(dict[Any, Any], value)
        return {
            item_key: _sanitize_value(item_value, key=str(item_key), parent_key=key)
            for item_key, item_value in typed_value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(item, parent_key=key) for item in cast(list[Any], value)]
    if isinstance(value, str):
        return _redact_observability_text(value)
    return value


def _sanitize_sensitive_container(key: str, value: Any, *, parent_key: str | None = None) -> Any:
    normalized = key.lower()
    if normalized == "request" and isinstance(value, dict):
        typed_value = cast(dict[Any, Any], value)
        return {
            item_key: _sanitize_value(item_value, key=str(item_key), parent_key=normalized)
            for item_key, item_value in typed_value.items()
        }
    if normalized in {"data", "body", "raw_body", "form", "json"} and parent_key == "request":
        return "***"
    if normalized == "headers" and isinstance(value, dict):
        typed_value = cast(dict[Any, Any], value)
        return {
            header: "***"
            if str(header).lower() in SENSITIVE_HEADER_NAMES
            else _sanitize_value(item)
            for header, item in typed_value.items()
        }
    if normalized in {"cookies", "query_string"}:
        return "***"
    return redact_metadata(value)


def _is_sensitive_event_key(key: str) -> bool:
    normalized = key.lower()
    compact = "".join(char for char in normalized if char.isalnum())
    words = _key_words(key)
    word_set = set(words)
    sensitive_compact_names = {item.replace("_", "") for item in SENSITIVE_FIELD_NAMES}
    if normalized in SENSITIVE_FIELD_NAMES or compact in sensitive_compact_names:
        return True
    if not words:
        return False
    if compact in {"sessionid", "sessiontoken", "sessioncookie"}:
        return True
    if any(word in word_set for word in {"password", "token", "jwt", "secret"}):
        return True
    if _contains_word_sequence(words, ("api", "hash")):
        return True
    if _contains_word_sequence(words, ("auth", "code")):
        return True
    if _contains_word_sequence(words, ("two", "factor", "password")):
        return True
    if "phone" in word_set:
        return True
    if "dsn" in word_set and words[-1] == "dsn":
        return True
    if "tdlib" in word_set and word_set.intersection(
        {"path", "root", "directory", "database", "files", "session", "library"}
    ):
        return True
    if "telegram" in word_set and word_set.intersection(
        {"api", "hash", "phone", "session", "token", "password"}
    ):
        return True
    if word_set.intersection({"s3", "b2", "supabase"}) and word_set.intersection(
        {"access", "key", "secret", "token", "password", "role", "jwt"}
    ):
        return True
    return is_sensitive_key(key) and not any(
        safe_fragment in compact for safe_fragment in ("statuscode", "errorcode", "sessioncount")
    )


def _redact_observability_text(value: str) -> str:
    redacted = redact_text(value)
    redacted = TDJSON_LIBRARY_PATTERN.sub("***", redacted)
    return redacted


def _key_words(key: str) -> list[str]:
    with_word_boundaries = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    return [word for word in re.split(r"[^a-z0-9]+", with_word_boundaries.lower()) if word]


def _contains_word_sequence(words: list[str], sequence: tuple[str, ...]) -> bool:
    if len(words) < len(sequence):
        return False
    return any(
        tuple(words[index : index + len(sequence)]) == sequence
        for index in range(len(words) - len(sequence) + 1)
    )


def _log_observability_init_error(exc: Exception) -> None:
    try:
        from app.logging_utils import log_warn

        log_warn("sentry_observability_init_failed", error_class=exc.__class__.__name__)
    except Exception:
        return
