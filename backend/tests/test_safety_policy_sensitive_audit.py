from __future__ import annotations

import pytest

from app.main import app
from app.models import DEFAULT_LOCAL_USER_ID, DEFAULT_LOCAL_WORKSPACE_ID, SensitiveAuditEvent
from app.services.auth_context import AuthContext, get_current_auth_context


def _auth(role: str = "admin") -> AuthContext:
    return AuthContext(
        user_id=DEFAULT_LOCAL_USER_ID,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role=role,
        auth_source="test",
    )


@pytest.fixture()
def admin_client(app_client):
    app.dependency_overrides[get_current_auth_context] = lambda: _auth("admin")
    return app_client


def _audit_events(db_session) -> list[SensitiveAuditEvent]:
    return db_session.query(SensitiveAuditEvent).order_by(SensitiveAuditEvent.created_at).all()


def test_patch_no_changes_skips_sensitive_audit(admin_client, db_session) -> None:
    response = admin_client.patch("/api/safety-policy", json={"mode": "balanced"})

    assert response.status_code == 200
    assert _audit_events(db_session) == []


def test_patch_one_field_records_sensitive_audit_diff(admin_client, db_session) -> None:
    response = admin_client.patch("/api/safety-policy", json={"delay_multiplier": 1.25})

    assert response.status_code == 200
    event = db_session.query(SensitiveAuditEvent).one()
    assert event.workspace_id == DEFAULT_LOCAL_WORKSPACE_ID
    assert event.actor_user_id == DEFAULT_LOCAL_USER_ID
    assert event.action == "workspace_safety_policy.updated"
    assert event.entity_type == "workspace_safety_policy"
    assert event.account_id is None
    assert event.metadata_json == {
        "changed_fields": ["delay_multiplier"],
        "old": {"delay_multiplier": 1.0},
        "new": {"delay_multiplier": 1.25},
    }


def test_patch_consecutive_failure_threshold_records_sensitive_audit_diff(
    admin_client, db_session
) -> None:
    response = admin_client.patch(
        "/api/safety-policy",
        json={"consecutive_failure_threshold": 5},
    )

    assert response.status_code == 200
    event = db_session.query(SensitiveAuditEvent).one()
    assert event.metadata_json == {
        "changed_fields": ["consecutive_failure_threshold"],
        "old": {"consecutive_failure_threshold": None},
        "new": {"consecutive_failure_threshold": 5},
    }


def test_patch_multiple_fields_records_sensitive_audit_diff(admin_client, db_session) -> None:
    response = admin_client.patch("/api/safety-policy", json={"mode": "conservative"})

    assert response.status_code == 200
    event = db_session.query(SensitiveAuditEvent).one()
    assert event.metadata_json == {
        "changed_fields": [
            "mode",
            "delay_multiplier",
            "typing_chars_per_minute_min",
            "typing_chars_per_minute_max",
            "profile_view_probability",
            "scroll_probability",
            "typo_probability",
            "message_deletion_probability",
            "quiet_hours_local_start",
            "quiet_hours_local_end",
            "min_warmup_days",
            "min_account_age_hours",
            "auto_pause_on_flood_wait_count",
            "auto_pause_on_deleted_comments_count",
        ],
        "old": {
            "mode": "balanced",
            "delay_multiplier": 1.0,
            "typing_chars_per_minute_min": 100,
            "typing_chars_per_minute_max": 150,
            "profile_view_probability": 0.7,
            "scroll_probability": 0.3,
            "typo_probability": 0.05,
            "message_deletion_probability": 0.02,
            "quiet_hours_local_start": 120,
            "quiet_hours_local_end": 360,
            "min_warmup_days": 3,
            "min_account_age_hours": 24,
            "auto_pause_on_flood_wait_count": 3,
            "auto_pause_on_deleted_comments_count": 5,
        },
        "new": {
            "mode": "conservative",
            "delay_multiplier": 1.5,
            "typing_chars_per_minute_min": 40,
            "typing_chars_per_minute_max": 60,
            "profile_view_probability": 0.9,
            "scroll_probability": 0.5,
            "typo_probability": 0.08,
            "message_deletion_probability": 0.03,
            "quiet_hours_local_start": 60,
            "quiet_hours_local_end": 420,
            "min_warmup_days": 7,
            "min_account_age_hours": 72,
            "auto_pause_on_flood_wait_count": 1,
            "auto_pause_on_deleted_comments_count": 2,
        },
    }


def test_patch_non_admin_returns_403_without_sensitive_audit(app_client, db_session) -> None:
    app.dependency_overrides[get_current_auth_context] = lambda: _auth("operator")

    response = app_client.patch("/api/safety-policy", json={"delay_multiplier": 1.25})

    assert response.status_code == 403
    assert response.json()["error_code"] == "ROLE_FORBIDDEN"
    assert _audit_events(db_session) == []
