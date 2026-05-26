from __future__ import annotations

from typing import Any

from app.db import Base
from app.main import app
from app.services.database import create_sqlite_test_session_factory

from tests.helpers.app import app_client as app_client_for_session


def test_static_bulk_target_route_rejects_unsupported_method_with_405(app_client) -> None:
    response = app_client.delete(
        "/api/neuro-commenting/campaigns/"
        "e3e70682-c209-1cac-a29f-6fbed82c07cd/targets/bulk"
    )

    assert response.status_code == 405
    assert response.headers["allow"] == "POST"


def test_channel_rule_create_schema_exposes_only_create_supported_rule_types() -> None:
    schema = app.openapi()
    rule_type_schema = schema["components"]["schemas"]["NeuroChannelRuleCreate"][
        "properties"
    ]["rule_type"]

    assert rule_type_schema["enum"] == ["blacklist", "whitelist"]


def test_safety_policy_rejects_explicit_null_for_required_fields(app_client) -> None:
    payload: dict[str, Any] = {
        "mode": None,
        "delay_multiplier": None,
        "profile_view_probability": None,
        "scroll_probability": None,
        "typo_probability": None,
        "message_deletion_probability": None,
        "require_warmup_before_commenting": None,
        "min_warmup_days": None,
        "require_healthy_proxy": None,
        "min_account_age_hours": None,
        "auto_pause_on_flood_wait_count": None,
        "auto_pause_on_deleted_comments_count": None,
        "quarantine_hours_on_flood_wait": None,
    }

    response = app_client.patch("/api/safety-policy", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    rejected_fields = {error["field"] for error in body["field_errors"]}
    assert "delay_multiplier" in rejected_fields
    assert "message_deletion_probability" in rejected_fields


def test_safety_policy_rejects_boolean_probability(app_client) -> None:
    response = app_client.patch(
        "/api/safety-policy",
        json={"message_deletion_probability": False},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(
        error["field"] == "message_deletion_probability" for error in body["field_errors"]
    )


def test_safety_policy_allows_null_for_nullable_fields(app_client) -> None:
    response = app_client.patch(
        "/api/safety-policy",
        json={
            "typing_chars_per_minute_min": None,
            "typing_chars_per_minute_max": None,
            "quiet_hours_local_start": None,
            "quiet_hours_local_end": None,
            "consecutive_failure_threshold": None,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["typing_chars_per_minute_min"] is None
    assert body["typing_chars_per_minute_max"] is None
    assert body["quiet_hours_local_start"] is None
    assert body["quiet_hours_local_end"] is None
    assert body["consecutive_failure_threshold"] is None


def test_notification_webhook_schema_requires_https() -> None:
    schema = app.openapi()
    url_schema = schema["components"]["schemas"]["WorkspaceNotificationSettingsUpdate"][
        "properties"
    ]["notification_webhook_url"]

    variants = url_schema.get("anyOf", [url_schema])
    string_variant = next(item for item in variants if item.get("type") == "string")
    assert string_variant["pattern"] == "^https://"


def test_notification_webhook_rejects_non_https_url() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    try:
        with app_client_for_session(session_factory, role="admin") as client:
            response = client.patch(
                "/api/workspaces/00000000-0000-0000-0000-000000000001/"
                "notification-settings",
                json={"notification_webhook_url": "http://example.test/hook"},
            )
    finally:
        engine.dispose()

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(
        error["field"] == "notification_webhook_url" for error in body["field_errors"]
    )
