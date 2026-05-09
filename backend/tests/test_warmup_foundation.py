from app.config import Settings
from app.models import WarmupEvent, WarmupSession, WarmupStatus, WarmupStrategy, WarmupTaskRun


def test_warmup_models_match_foundation_tables() -> None:
    assert WarmupStrategy.__tablename__ == "warmup_strategy"
    assert WarmupSession.__tablename__ == "warmup_session"
    assert WarmupEvent.__tablename__ == "warmup_event"
    assert WarmupTaskRun.__tablename__ == "warmup_task_run"
    assert WarmupStatus.SCHEDULED == "scheduled"


def test_warmup_settings_default_to_safe_dry_run() -> None:
    settings = Settings()

    assert settings.warmup_workers_enabled is False
    assert settings.warmup_dry_run is True
    assert settings.warmup_default_cadence_hours == 24
    assert settings.warmup_max_consecutive_failures == 3


def test_warmup_router_uses_expected_prefix() -> None:
    from app.api.warmup import router

    assert router.prefix == "/api/warmup"


# ---------------------------------------------------------------------------
# Warmup event payload sanitization
# ---------------------------------------------------------------------------


def test_warmup_event_payload_redacts_all_sensitive_keys() -> None:
    from app.services.warmup import SENSITIVE_EVENT_KEYS, _sanitize_event_payload

    payload = {key: f"secret-{key}" for key in sorted(SENSITIVE_EVENT_KEYS)}
    sanitized = _sanitize_event_payload(payload)

    for key in SENSITIVE_EVENT_KEYS:
        assert sanitized[key] == "[redacted]", f"{key} was not redacted"


def test_warmup_event_payload_preserves_safe_action_keys() -> None:
    from app.services.warmup import _sanitize_event_payload

    payload = {
        "action_type": "send_message",
        "error_code": "PEER_FLOOD",
        "status": "ok",
        "phase": "shadow",
        "channel_id": -1001234567890,
        "duration_ms": 42,
    }
    sanitized = _sanitize_event_payload(payload)

    assert sanitized == payload


def test_warmup_event_payload_redacts_nested_sensitive_keys() -> None:
    from app.services.warmup import _sanitize_event_payload

    payload = {
        "metadata": {
            "proxy_password": "p4ss",
            "api_hash": "deadbeef",
            "provider": "builtin",
        },
        "action_type": "join_channel",
    }
    sanitized = _sanitize_event_payload(payload)

    assert sanitized["metadata"]["proxy_password"] == "[redacted]"
    assert sanitized["metadata"]["api_hash"] == "[redacted]"
    assert sanitized["metadata"]["provider"] == "builtin"
    assert sanitized["action_type"] == "join_channel"


def test_warmup_event_payload_handles_empty_and_none() -> None:
    from app.services.warmup import _sanitize_event_payload

    assert _sanitize_event_payload({}) == {}

    payload_with_none_value = {"action_type": None, "password": "secret"}
    sanitized = _sanitize_event_payload(payload_with_none_value)
    assert sanitized["action_type"] is None
    assert sanitized["password"] == "[redacted]"
