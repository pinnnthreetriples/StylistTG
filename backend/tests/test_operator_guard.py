from fastapi.testclient import TestClient

from app.config import settings
from app.main import app, _configured_cors_origins, _is_local_client


class DummyClient:
    host = "203.0.113.10"


class DummyRequest:
    client = DummyClient()


class LocalIpv4MappedClient:
    host = "::ffff:127.0.0.1"


class LocalIpv4MappedRequest:
    client = LocalIpv4MappedClient()


def test_operator_guard_marks_remote_client_non_local() -> None:
    assert _is_local_client(DummyRequest()) is False


def test_operator_guard_allows_ipv4_mapped_localhost() -> None:
    assert _is_local_client(LocalIpv4MappedRequest()) is True


def test_operator_guard_uses_configurable_allowed_hosts(monkeypatch) -> None:
    monkeypatch.setattr(settings, "operator_allowed_client_hosts", "203.0.113.10")

    assert _is_local_client(DummyRequest()) is True


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


def test_operator_guard_allows_public_runtime_diagnostics(monkeypatch) -> None:
    monkeypatch.setattr(settings, "enforce_localhost_only", True)
    monkeypatch.setattr(settings, "operator_allowed_client_hosts", "127.0.0.1")
    monkeypatch.setattr(
        "app.api.diagnostics.build_runtime_diagnostics",
        lambda: {"database": "ok", "redis": "ok", "tdlib": "not_configured"},
    )
    client = TestClient(app)

    runtime = client.get("/diagnostics/runtime")
    frontend_summary = client.get("/diagnostics/frontend-summary")

    assert runtime.status_code == 200
    assert frontend_summary.status_code == 403


def test_worker_diagnostics_is_public_safe_metadata(monkeypatch) -> None:
    monkeypatch.setattr(settings, "enforce_localhost_only", True)
    monkeypatch.setattr(settings, "tdlib_database_root", "C:/real/session/db")
    monkeypatch.setattr(settings, "tdlib_files_root", "C:/real/session/files")
    client = TestClient(app)

    response = client.get("/api/workers/diagnostics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "redis_rq"
    assert {"auth_jobs", "profile_jobs", "warmup_jobs"}.issubset(
        {queue["name"] for queue in payload["queues"]}
    )
    serialized = str(payload)
    assert "session/db" not in serialized
    assert "session/files" not in serialized
    assert "rediss://" not in serialized


def test_cors_origin_parser_trims_configured_pages_origins(monkeypatch) -> None:
    monkeypatch.setattr(
        settings,
        "cors_origins",
        "https://stylisttg-dashboard.pages.dev, https://0df59c45.stylisttg-dashboard.pages.dev",
    )

    assert _configured_cors_origins() == [
        "https://stylisttg-dashboard.pages.dev",
        "https://0df59c45.stylisttg-dashboard.pages.dev",
    ]
