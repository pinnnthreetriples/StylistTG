# test-analyzer: disable-file=TQA050 reason="bare response.json() truthiness check; tightened to exact body assertion in #263 sweep"

from tests.helpers.app import app_client
from tests.helpers.factories import make_session


def test_execution_policy_accepts_product_cooldowns_and_advanced_policy(monkeypatch) -> None:
    from app.config import settings as api_settings

    monkeypatch.setattr(api_settings, "profile_job_cooldown_seconds", 120)
    monkeypatch.setattr(api_settings, "username_cooldown_seconds", 1800)
    monkeypatch.setattr(api_settings, "profile_music_cooldown_seconds", 900)
    monkeypatch.setattr(api_settings, "unknown_capability_policy", "warning_only")
    monkeypatch.setattr(api_settings, "recent_failure_policy", "warning_only")
    monkeypatch.setattr(api_settings, "fresh_validity_required", "if_stale")
    monkeypatch.setattr(api_settings, "fresh_validity_max_age_minutes", 30)
    monkeypatch.setattr(api_settings, "manual_hard_blocker_override_enabled", False)
    session_factory, _engine = make_session()

    with app_client(session_factory, role="admin") as client:
        response = client.patch(
            "/api/settings/execution-policy",
            json={
                "profile_job_cooldown_seconds": 60,
                "username_cooldown_seconds": 1800,
                "profile_music_cooldown_seconds": 900,
                "unknown_capability_policy": "block_live_execution",
                "recent_failure_policy": "cooldown",
                "fresh_validity_required": "if_stale",
                "fresh_validity_max_age_minutes": 20,
                "manual_hard_blocker_override_enabled": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["username_cooldown_seconds"] == 1800
    assert payload["profile_music_cooldown_seconds"] == 900
    assert payload["unknown_capability_policy"] == "block_live_execution"
    assert payload["manual_hard_blocker_override_enabled"] is True
    assert "AUTH_KEY_UNREGISTERED" in payload["non_overridable_blockers"]


def test_execution_policy_keeps_legacy_profile_job_cooldown_upper_bound(monkeypatch) -> None:
    from app.config import settings as api_settings

    monkeypatch.setattr(api_settings, "profile_job_cooldown_seconds", 120)
    session_factory, _engine = make_session()

    with app_client(session_factory, role="admin") as client:
        response = client.patch(
            "/api/settings/execution-policy",
            json={"profile_job_cooldown_seconds": 86400},
        )

    assert response.status_code == 422
    body = response.json()
    # StylistTG validation envelope: error_code + field_errors[].field naming
    # the offending request field.
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(
        "profile_job_cooldown_seconds" in (entry.get("field") or "")
        for entry in body["field_errors"]
    ), f"expected profile_job_cooldown_seconds field error, got body={body!r}"
