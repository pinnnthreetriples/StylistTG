from __future__ import annotations

import pytest

from app.main import app
from app.models import (
    DEFAULT_LOCAL_USER_ID,
    DEFAULT_LOCAL_WORKSPACE_ID,
    SensitiveAuditEvent,
    WorkspaceSafetyPolicy,
)
from app.services.auth_context import AuthContext, get_current_auth_context
from app.services.workspace_safety_policy import compute_diff


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


def test_get_creates_balanced_default_when_missing(admin_client, db_session) -> None:
    response = admin_client.get("/api/safety-policy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workspace_id"] == DEFAULT_LOCAL_WORKSPACE_ID
    assert payload["mode"] == "balanced"
    assert payload["delay_multiplier"] == 1.0
    assert payload["typing_chars_per_minute_min"] == 100
    assert payload["typing_chars_per_minute_max"] == 150
    assert payload["quiet_hours_local_start"] == 120
    assert payload["quiet_hours_local_end"] == 360

    row = db_session.query(WorkspaceSafetyPolicy).one()
    assert row.mode == "balanced"


_CONSERVATIVE_EXPECTED = {
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
    "require_warmup_before_commenting": True,
    "min_warmup_days": 7,
    "require_healthy_proxy": True,
    "min_account_age_hours": 72,
    "auto_pause_on_flood_wait_count": 1,
    "auto_pause_on_deleted_comments_count": 2,
    "quarantine_hours_on_flood_wait": 24,
}

_AGGRESSIVE_EXPECTED = {
    "mode": "aggressive",
    "delay_multiplier": 0.7,
    "typing_chars_per_minute_min": None,
    "typing_chars_per_minute_max": None,
    "profile_view_probability": 0.3,
    "scroll_probability": 0.0,
    "typo_probability": 0.02,
    "message_deletion_probability": 0.01,
    "quiet_hours_local_start": None,
    "quiet_hours_local_end": None,
    "require_warmup_before_commenting": False,
    "min_warmup_days": 1,
    "require_healthy_proxy": False,
    "min_account_age_hours": 0,
    "auto_pause_on_flood_wait_count": 5,
    "auto_pause_on_deleted_comments_count": 10,
}


def test_patch_conservative_applies_preset_defaults(admin_client) -> None:
    response = admin_client.patch("/api/safety-policy", json={"mode": "conservative"})

    assert response.status_code == 200
    payload = response.json()
    assert {k: payload[k] for k in _CONSERVATIVE_EXPECTED} == _CONSERVATIVE_EXPECTED


def test_patch_aggressive_relaxes_protective_parameters(admin_client) -> None:
    response = admin_client.patch("/api/safety-policy", json={"mode": "aggressive"})

    assert response.status_code == 200
    payload = response.json()
    assert {k: payload[k] for k in _AGGRESSIVE_EXPECTED} == _AGGRESSIVE_EXPECTED


def test_patch_non_admin_returns_403(app_client) -> None:
    app.dependency_overrides[get_current_auth_context] = lambda: _auth("operator")

    response = app_client.patch("/api/safety-policy", json={"mode": "conservative"})

    assert response.status_code == 403
    body = response.json()
    assert "detail" in body or "error_code" in body


def test_patch_invalid_mode_returns_422(admin_client) -> None:
    response = admin_client.patch("/api/safety-policy", json={"mode": "reckless"})

    assert response.status_code == 422
    body = response.json()
    assert "detail" in body or "error_code" in body


def test_compute_diff_only_returns_changed_public_policy_fields() -> None:
    old = {
        "id": "policy-1",
        "workspace_id": DEFAULT_LOCAL_WORKSPACE_ID,
        "mode": "balanced",
        "delay_multiplier": 1.0,
        "require_healthy_proxy": True,
        "updated_at": "2026-05-21T00:00:00Z",
    }
    new = {
        **old,
        "delay_multiplier": 1.25,
        "require_healthy_proxy": False,
        "updated_at": "2026-05-21T00:01:00Z",
    }

    assert compute_diff(old, new) == {
        "changed_fields": ["delay_multiplier", "require_healthy_proxy"],
        "old": {
            "delay_multiplier": 1.0,
            "require_healthy_proxy": True,
        },
        "new": {
            "delay_multiplier": 1.25,
            "require_healthy_proxy": False,
        },
    }


def test_patch_records_sensitive_audit_event(admin_client, db_session) -> None:
    response = admin_client.patch("/api/safety-policy", json={"mode": "conservative"})

    assert response.status_code == 200
    event = db_session.query(SensitiveAuditEvent).one()
    assert event.workspace_id == DEFAULT_LOCAL_WORKSPACE_ID
    assert event.actor_user_id == DEFAULT_LOCAL_USER_ID
    assert event.action == "workspace_safety_policy.updated"
    assert event.entity_type == "workspace_safety_policy"
    assert event.metadata_json["new"]["mode"] == "conservative"
