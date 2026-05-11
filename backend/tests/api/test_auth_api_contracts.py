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


def test_auth_runtime_mode_toggle_updates_backend_settings() -> None:
    session_factory, _engine = make_session()
    original_test_dc = app.dependency_overrides.get("unused")

    with app_client(session_factory, role="admin") as client:
        get_response = client.get("/api/auth/runtime-mode")
        assert get_response.status_code == 200
        before = get_response.json()

        enable_response = client.patch("/api/auth/runtime-mode", json={"tdlib_use_test_dc": True})
        assert enable_response.status_code == 200
        assert enable_response.json() == {
            "tdlib_use_test_dc": True,
            "tdlib_production_auth_enabled": False,
        }

        disable_response = client.patch("/api/auth/runtime-mode", json={"tdlib_use_test_dc": False})
        assert disable_response.status_code == 200
        assert disable_response.json() == {
            "tdlib_use_test_dc": False,
            "tdlib_production_auth_enabled": True,
        }

        client.patch(
            "/api/auth/runtime-mode", json={"tdlib_use_test_dc": before["tdlib_use_test_dc"]}
        )
    assert original_test_dc is None
