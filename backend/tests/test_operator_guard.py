from fastapi.testclient import TestClient

from app.config import settings
from app.main import app, _is_local_client


class DummyClient:
    host = "203.0.113.10"


class DummyRequest:
    client = DummyClient()


def test_operator_guard_marks_remote_client_non_local() -> None:
    assert _is_local_client(DummyRequest()) is False


def test_operator_token_required_for_mutating_requests(monkeypatch) -> None:
    monkeypatch.setattr(settings, "operator_api_token", "secret-token")
    client = TestClient(app)

    response = client.patch("/api/auth/runtime-mode", json={"tdlib_use_test_dc": False})

    assert response.status_code == 401


def test_operator_token_allows_mutating_requests(monkeypatch) -> None:
    monkeypatch.setattr(settings, "operator_api_token", "secret-token")
    client = TestClient(app)

    response = client.patch(
        "/api/auth/runtime-mode",
        headers={"X-Operator-Token": "secret-token"},
        json={"tdlib_use_test_dc": False},
    )

    assert response.status_code == 200
