from fastapi.testclient import TestClient

from app.db import Base
from app.main import app
from app.models import AccountState
from app.services.runtime_diagnostics import build_runtime_diagnostics
from app.services.accounts import create_account
from app.services.database import create_sqlite_test_session_factory

from conftest import FakeExecutionUsableAdapter, FakeProfileSyncAdapter, override_app_session


def test_runtime_diagnostics_and_refresh_endpoint(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        account.account_state = AccountState.AUTHORIZED_READY
        session.commit()
        account_id = account.id

    override_app_session(session_factory)
    monkeypatch.setattr(
        "app.api.accounts.build_profile_execution_adapter",
        lambda: FakeExecutionUsableAdapter(ok=True),
    )
    monkeypatch.setattr(
        "app.api.accounts.build_profile_sync_adapter",
        lambda: FakeProfileSyncAdapter(),
    )
    monkeypatch.setattr(
        "app.main.build_runtime_diagnostics",
        lambda: {"database": "ok", "redis": "ok", "tdlib": "not_configured"},
    )
    monkeypatch.setattr(
        "app.services.runtime_diagnostics._tdlib_credentials_present",
        lambda: False,
    )
    client = TestClient(app)

    refresh = client.post(f"/api/accounts/{account_id}/refresh-runtime")
    assert refresh.status_code == 200
    assert refresh.json()["account_state"] == "execution_usable"
    assert refresh.json()["is_execution_usable"] is True

    diagnostics = client.get(f"/api/accounts/{account_id}/runtime-diagnostics")
    assert diagnostics.status_code == 200
    payload = diagnostics.json()
    assert payload["account_state"] == "execution_usable"
    assert payload["can_start_profile_job"] is True
    assert payload["runtime_health"] == "ready"
    assert payload["tdlib_configured"] is False
    assert payload["manual_intervention_required"] is False
    assert payload["recovery_marker"] == "execution_policy:ready"
    assert payload["lock_owner"] is None
    assert payload["lock_epoch"] == 0

    app.dependency_overrides.clear()


def test_header_account_runtime_endpoints_do_not_require_account_id_in_url(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        account.account_state = AccountState.AUTHORIZED_READY
        session.commit()
        account_id = account.id

    override_app_session(session_factory)
    monkeypatch.setattr(
        "app.api.accounts.build_profile_execution_adapter",
        lambda: FakeExecutionUsableAdapter(ok=True),
    )
    monkeypatch.setattr(
        "app.api.accounts.build_profile_sync_adapter",
        lambda: FakeProfileSyncAdapter(),
    )
    client = TestClient(app)
    headers = {"X-Account-Id": account_id}

    assert client.get("/api/accounts/auth-state", headers=headers).status_code == 200
    assert client.post("/api/accounts/refresh-runtime", headers=headers).status_code == 200
    assert client.get("/api/accounts/runtime-diagnostics", headers=headers).status_code == 200
    assert client.get("/api/accounts/jobs", headers=headers).status_code == 200

    app.dependency_overrides.clear()


def test_ready_endpoint_checks_database_and_redis(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.build_runtime_diagnostics",
        lambda: {"database": "ok", "redis": "ok", "tdlib": "not_configured"},
    )
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoint_is_liveness_only(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.build_runtime_diagnostics",
        lambda: {"database": "down", "redis": "down", "tdlib": "not_configured"},
    )
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_endpoint_returns_503_when_redis_is_down(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.build_runtime_diagnostics",
        lambda: {"database": "ok", "redis": "down", "tdlib": "not_configured"},
    )
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_ready_endpoint_returns_503_when_database_is_down(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.build_runtime_diagnostics",
        lambda: {"database": "down", "redis": "ok", "tdlib": "not_configured"},
    )
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_ready_endpoint_does_not_fail_on_tdlib_not_configured_in_mock(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.build_runtime_diagnostics",
        lambda: {"database": "ok", "redis": "ok", "tdlib": "not_configured"},
    )
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"status": "ok"}
    assert "tdlib" not in payload
    assert "database" not in payload
    assert "redis" not in payload


def test_runtime_diagnostics_uses_short_redis_timeouts(monkeypatch) -> None:
    captured_kwargs = {}

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, statement):
            return None

    class FakeRedis:
        def ping(self):
            return True

    def fake_from_url(url, **kwargs):
        captured_kwargs.update(kwargs)
        return FakeRedis()

    monkeypatch.setattr("app.services.runtime_diagnostics.SessionLocal", FakeSession)
    monkeypatch.setattr("app.services.runtime_diagnostics.Redis.from_url", fake_from_url)

    diagnostics = build_runtime_diagnostics()

    assert diagnostics["redis"] == "ok"
    assert captured_kwargs["socket_connect_timeout"] <= 1
    assert captured_kwargs["socket_timeout"] <= 1
