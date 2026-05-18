from fastapi.testclient import TestClient

from app.db import Base
from app.main import app
from app.services.database import create_sqlite_test_session_factory

from conftest import FakeTdlibAuthAdapter, override_app_session
from tests.helpers.app import app_client
from tests.helpers.factories import make_session


def test_otp_api_contract_start_confirm_and_auth_state(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    override_app_session(session_factory)
    monkeypatch.setattr("app.api.auth.build_tdlib_auth_adapter", lambda: FakeTdlibAuthAdapter())
    client = TestClient(app)

    try:
        start_response = client.post("/api/auth/otp/start", json={"phone_number": "+15550102000"})
        assert start_response.status_code == 201
        start_payload = start_response.json()
        assert start_payload["orchestration_state"] == "awaiting_code"
        assert start_payload["needs_code"] is True

        confirm_response = client.post(
            "/api/auth/otp/confirm",
            json={"account_id": start_payload["account_id"], "code": "12345"},
        )
        assert confirm_response.status_code == 200
        confirm_payload = confirm_response.json()
        assert confirm_payload["orchestration_state"] == "authorized_ready"
        assert confirm_payload["telegram_user_id"] == "123456"

        state_response = client.get(f"/api/accounts/{start_payload['account_id']}/auth-state")
        assert state_response.status_code == 200
        assert state_response.json()["runtime_health"] == "ready"
    finally:
        app.dependency_overrides.clear()


def test_auth_runtime_mode_toggle_persists_without_mutating_backend_settings() -> None:
    session_factory, _engine = make_session()
    from app.config import settings as auth_settings

    original_test_dc = auth_settings.tdlib_use_test_dc
    original_production_auth = auth_settings.tdlib_production_auth_enabled

    with app_client(session_factory, role="admin") as client:
        get_response = client.get("/api/auth/runtime-mode")
        assert get_response.status_code == 200

        enable_response = client.patch("/api/auth/runtime-mode", json={"tdlib_use_test_dc": True})
        assert enable_response.status_code == 200
        assert enable_response.json() == {
            "tdlib_use_test_dc": True,
            "tdlib_production_auth_enabled": False,
        }
        assert auth_settings.tdlib_use_test_dc is original_test_dc
        assert auth_settings.tdlib_production_auth_enabled is original_production_auth

        disable_response = client.patch("/api/auth/runtime-mode", json={"tdlib_use_test_dc": False})
        assert disable_response.status_code == 200
        assert disable_response.json() == {
            "tdlib_use_test_dc": False,
            "tdlib_production_auth_enabled": True,
        }

        repeat_get_response = client.get("/api/auth/runtime-mode")
        assert repeat_get_response.status_code == 200
        assert repeat_get_response.json() == disable_response.json()

    assert auth_settings.tdlib_use_test_dc is original_test_dc
    assert auth_settings.tdlib_production_auth_enabled is original_production_auth


def test_auth_runtime_mode_rejects_numeric_boolean(app_client) -> None:
    response = app_client.patch("/api/auth/runtime-mode", json={"tdlib_use_test_dc": 0})

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(error["field"] == "tdlib_use_test_dc" for error in body["field_errors"])


def test_execution_policy_rejects_numeric_boolean(app_client) -> None:
    response = app_client.patch(
        "/api/settings/execution-policy",
        json={"manual_hard_blocker_override_enabled": 0},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(
        error["field"] == "manual_hard_blocker_override_enabled" for error in body["field_errors"]
    )


def test_execution_policy_rejects_boolean_cooldown_seconds(app_client) -> None:
    response = app_client.patch(
        "/api/settings/execution-policy",
        json={"story_delete_cooldown_seconds": False},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(error["field"] == "story_delete_cooldown_seconds" for error in body["field_errors"])


def test_execution_policy_rejects_explicit_null_cooldown_seconds(app_client) -> None:
    response = app_client.patch(
        "/api/settings/execution-policy",
        json={"profile_music_cooldown_seconds": None},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(
        error["field"].startswith("profile_music_cooldown_seconds")
        for error in body["field_errors"]
    )


def test_auth_batch_create_rejects_empty_items(app_client) -> None:
    response = app_client.post(
        "/api/auth-batches",
        json={"idempotency_key": "batch-1", "items": []},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(error["field"] == "items" for error in body["field_errors"])


def test_auth_batch_create_rejects_invalid_phone_at_schema_boundary(app_client) -> None:
    response = app_client.post(
        "/api/auth-batches",
        json={"idempotency_key": "batch-1", "items": [{"phone_number": "000"}]},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(error["field"] == "items.0.phone_number" for error in body["field_errors"])


def test_auth_batch_create_returns_rfc3339_datetimes(app_client) -> None:
    response = app_client.post(
        "/api/auth-batches",
        json={
            "idempotency_key": "batch-1",
            "items": [{"phone_number": "+15550102000"}],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["batch"]["created_at"].endswith("Z") or "+" in body["batch"]["created_at"]
    assert body["items"][0]["updated_at"].endswith("Z") or "+" in body["items"][0]["updated_at"]


def test_otp_start_rejects_non_international_phone_at_schema_boundary(app_client) -> None:
    response = app_client.post("/api/auth/otp/start", json={"phone_number": ""})

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(error["field"] == "phone_number" for error in body["field_errors"])


def test_account_action_gate_rejects_unknown_action_type_at_schema_boundary(app_client) -> None:
    response = app_client.get("/api/accounts/0/action-gate", params={"action_type": ""})

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert any(error["field"] == "query.action_type" for error in body["field_errors"])


def test_auth_session_create_returns_rfc3339_datetimes(app_client) -> None:
    response = app_client.post(
        "/api/accounts/auth-sessions",
        json={"phone_number": "+15550102000"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created_at"].endswith("Z") or "+" in body["created_at"]
