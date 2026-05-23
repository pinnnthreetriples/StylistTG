from __future__ import annotations

from app.observability import sentry
from app.observability.sentry import sanitize_sentry_event


def test_sentry_event_sanitizer_removes_sensitive_request_data() -> None:
    event = {
        "request": {
            "headers": {
                "authorization": "Bearer jwt-value",
                "cookie": "session=secret",
                "user-agent": "pytest",
            },
            "data": {"phone": "+79990000001", "code": "12345"},
            "query_string": "token=secret",
        },
        "extra": {
            "redis_url": "redis://:secret@localhost:6379/0",
            "tdlib_path": "C:/tdlib/tdjson.dll",
            "proxy_password": "secret",
        },
    }

    sanitized = sanitize_sentry_event(event)

    assert sanitized is not None
    assert sanitized["request"]["headers"]["authorization"] == "***"
    assert sanitized["request"]["headers"]["cookie"] == "***"
    assert sanitized["request"]["headers"]["user-agent"] == "pytest"
    assert sanitized["request"]["data"] == "***"
    assert sanitized["request"]["query_string"] == "***"
    assert sanitized["extra"]["redis_url"] == "***"
    assert sanitized["extra"]["tdlib_path"] == "***"
    assert sanitized["extra"]["proxy_password"] == "***"


def test_sentry_event_sanitizer_redacts_sensitive_text() -> None:
    event = {
        "message": "token=secret redis://user:pass@example.com/path",
        "extra": {"safe": "ok"},
    }

    sanitized = sanitize_sentry_event(event)

    assert sanitized is not None
    assert "secret" not in sanitized["message"]
    assert "pass" not in sanitized["message"]
    assert sanitized["extra"]["safe"] == "ok"


def test_sentry_event_sanitizer_preserves_breadcrumb_data() -> None:
    event = {
        "breadcrumbs": [
            {
                "type": "http",
                "data": {
                    "url": "https://example.test/api/ready",
                    "method": "GET",
                    "status_code": 503,
                },
            }
        ]
    }

    sanitized = sanitize_sentry_event(event)

    assert sanitized is not None
    assert sanitized["breadcrumbs"][0]["data"] == {
        "url": "https://example.test/api/ready",
        "method": "GET",
        "status_code": 503,
    }


def test_sentry_event_sanitizer_redacts_tdjson_library_paths_in_text() -> None:
    event = {
        "message": (
            "failed to load /usr/local/lib/libtdjson.so, "
            "C:\\Tools\\tdlib\\tdjson.dll and /opt/tdlib/libtdjson.dylib"
        )
    }

    sanitized = sanitize_sentry_event(event)

    assert sanitized is not None
    assert "libtdjson.so" not in sanitized["message"]
    assert "libtdjson.dylib" not in sanitized["message"]
    assert "tdjson.dll" not in sanitized["message"]
    assert "/usr/local/lib" not in sanitized["message"]
    assert "/opt/tdlib" not in sanitized["message"]
    assert "C:\\Tools\\tdlib" not in sanitized["message"]


def test_sentry_event_sanitizer_handles_long_non_matching_path_text() -> None:
    message = "load failed " + "/".join(["not-tdjson"] * 5000)

    sanitized = sanitize_sentry_event({"message": message})

    assert sanitized is not None
    assert sanitized["message"] == message


def test_sentry_event_sanitizer_does_not_redact_common_status_keys() -> None:
    event = {
        "extra": {
            "statusCode": 503,
            "errorCode": "ECONNREFUSED",
            "obs_session_count": 2,
            "session_id": "secret-session",
        }
    }

    sanitized = sanitize_sentry_event(event)

    assert sanitized is not None
    assert sanitized["extra"]["statusCode"] == 503
    assert sanitized["extra"]["errorCode"] == "ECONNREFUSED"
    assert sanitized["extra"]["obs_session_count"] == 2
    assert sanitized["extra"]["session_id"] == "***"


def test_init_sentry_reports_live_when_already_initialized(monkeypatch) -> None:
    monkeypatch.setattr(sentry, "_initialized", True)

    assert sentry._init_sentry(dsn="https://token@example.com/1", integrations=()) is True


# ---------------------------------------------------------------------------
# Warmup-specific Sentry sanitization
# ---------------------------------------------------------------------------


def test_sentry_sanitizer_redacts_warmup_proxy_password_in_extras() -> None:
    event = {
        "extra": {
            "warmup_session_id": "ws_abc123",
            "proxy_password": "super-secret-proxy",
            "action_type": "send_message",
            "error_code": "PEER_FLOOD",
        }
    }

    sanitized = sanitize_sentry_event(event)

    assert sanitized is not None
    assert sanitized["extra"]["proxy_password"] == "***"
    assert sanitized["extra"]["warmup_session_id"] == "ws_abc123"
    assert sanitized["extra"]["action_type"] == "send_message"
    assert sanitized["extra"]["error_code"] == "PEER_FLOOD"


def test_sentry_sanitizer_preserves_warmup_diagnostic_keys() -> None:
    event = {
        "extra": {
            "action_type": "join_channel",
            "status": "ok",
            "phase": "shadow",
            "duration_ms": 1234,
            "channel_id": -1001234567890,
            "error_code": "CHAT_WRITE_FORBIDDEN",
            "circuit_breaker_tripped": True,
        }
    }

    sanitized = sanitize_sentry_event(event)

    assert sanitized is not None
    assert sanitized["extra"] == event["extra"]


def test_sentry_sanitizer_redacts_warmup_tdlib_fields() -> None:
    event = {
        "extra": {
            "tdlib_database_root": "/home/app/.tdlib/db",
            "tdlib_session_path": "/home/app/.tdlib/sessions/acct1",
            "telegram_api_hash": "deadbeefcafe1234",
            "telegram_phone": "+79990000001",
            "action_type": "read_history",
        }
    }

    sanitized = sanitize_sentry_event(event)

    assert sanitized is not None
    assert sanitized["extra"]["tdlib_database_root"] == "***"
    assert sanitized["extra"]["tdlib_session_path"] == "***"
    assert sanitized["extra"]["telegram_api_hash"] == "***"
    assert sanitized["extra"]["telegram_phone"] == "***"
    assert sanitized["extra"]["action_type"] == "read_history"


def test_sentry_sanitizer_redacts_raw_text_payload_in_warmup_context() -> None:
    event = {
        "message": (
            "warmup dispatch failed: password=leaked123 "
            "proxy_password: cleartext api_hash: abc123def"
        ),
    }

    sanitized = sanitize_sentry_event(event)

    assert sanitized is not None
    assert "leaked123" not in sanitized["message"]
    assert "cleartext" not in sanitized["message"]
    assert "abc123def" not in sanitized["message"]
