import pytest
from fastapi.testclient import TestClient

from app.db import Base
from app.main import app
from app.models import AccountState
from app.services.runtime_diagnostics import build_runtime_diagnostics
from app.services.accounts import create_account
from app.services.database import create_sqlite_test_session_factory

from conftest import FakeExecutionUsableAdapter, FakeProfileSyncAdapter, override_app_session


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Guarantee dependency_overrides are cleaned up after every test."""
    yield
    app.dependency_overrides.clear()


def _setup_account_with_session(monkeypatch, *, patch_diagnostics: bool = False):
    """Create a session factory + account and apply standard monkeypatches."""
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        account.account_state = AccountState.AUTHORIZED_READY
        session.commit()
        account_id = account.id
    override_app_session(session_factory)
    monkeypatch.setattr(
        "app.modules.account_shared.runtime.build_profile_execution_adapter",
        lambda: FakeExecutionUsableAdapter(ok=True),
    )
    monkeypatch.setattr(
        "app.modules.account_shared.runtime.build_profile_sync_adapter",
        lambda: FakeProfileSyncAdapter(),
    )
    if patch_diagnostics:
        monkeypatch.setattr(
            "app.main.build_runtime_diagnostics",
            lambda: {"database": "ok", "redis": "ok", "tdlib": "not_configured"},
        )
        monkeypatch.setattr(
            "app.services.runtime_diagnostics._tdlib_credentials_present",
            lambda: False,
        )
    return account_id


def test_runtime_diagnostics_and_refresh_endpoint(monkeypatch) -> None:
    account_id = _setup_account_with_session(monkeypatch, patch_diagnostics=True)
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
    account_id = _setup_account_with_session(monkeypatch)
    client = TestClient(app)
    headers = {"X-Account-Id": account_id}

    assert client.get("/api/accounts/auth-state", headers=headers).status_code == 200
    assert client.post("/api/accounts/refresh-runtime", headers=headers).status_code == 200
    assert client.get("/api/accounts/runtime-diagnostics", headers=headers).status_code == 200
    assert client.get("/api/accounts/jobs", headers=headers).status_code == 200

    app.dependency_overrides.clear()


def _patch_diagnostics(monkeypatch, *, database: str = "ok", redis: str = "ok"):
    """Monkeypatch build_runtime_diagnostics with the given component states."""
    monkeypatch.setattr(
        "app.main.build_runtime_diagnostics",
        lambda: {"database": database, "redis": redis, "tdlib": "not_configured"},
    )


@pytest.mark.parametrize(
    "endpoint,db,redis_state,expected_status,expected_body",
    [
        ("/ready", "ok", "ok", 200, {"status": "ok"}),
        ("/health", "down", "down", 200, {"status": "ok"}),
        ("/ready", "ok", "down", 503, {"status": "unavailable"}),
        ("/ready", "down", "ok", 503, {"status": "unavailable"}),
    ],
    ids=["ready-ok", "health-liveness", "ready-redis-down", "ready-db-down"],
)
def test_ready_health_endpoints(
    monkeypatch, endpoint, db, redis_state, expected_status, expected_body
) -> None:
    _patch_diagnostics(monkeypatch, database=db, redis=redis_state)
    client = TestClient(app)

    response = client.get(endpoint)

    assert response.status_code == expected_status
    assert response.json() == expected_body


def test_ready_endpoint_does_not_expose_internal_component_keys(monkeypatch) -> None:
    _patch_diagnostics(monkeypatch)
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

    def fake_redis_from_url(*, socket_connect_timeout, socket_timeout):
        captured_kwargs["socket_connect_timeout"] = socket_connect_timeout
        captured_kwargs["socket_timeout"] = socket_timeout
        return FakeRedis()

    monkeypatch.setattr("app.services.runtime_diagnostics.SessionLocal", FakeSession)
    monkeypatch.setattr("app.services.runtime_diagnostics.redis_from_url", fake_redis_from_url)

    diagnostics = build_runtime_diagnostics()

    assert diagnostics["redis"] == "ok"
    assert captured_kwargs["socket_connect_timeout"] <= 1
    assert captured_kwargs["socket_timeout"] <= 1
