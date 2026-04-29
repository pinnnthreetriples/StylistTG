from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.config import settings
from app.adapters.tdlib_auth import TdlibAuthResult, TdlibAuthStatus
from app.db import Base
from app.main import app
from app.models import Account, AccountRuntimeState, AccountState, AuthBatch, AuthBatchEvent, AuthBatchItem
from app.services.accounts import create_account
from app.services.auth_batches import PhoneInput, validate_batch_phones
from app.services.database import create_sqlite_test_session_factory

from conftest import override_app_session


class BatchFakeAuthAdapter:
    def __init__(self) -> None:
        self.started: list[tuple[str, str]] = []
        self.confirmed: list[tuple[str, str]] = []
        self.passwords: list[tuple[str, str]] = []
        self.start_result = TdlibAuthResult(
            status=TdlibAuthStatus.WAIT_CODE,
            account_state=AccountState.AWAITING_CODE,
            runtime_health="awaiting_code",
            needs_code=True,
            session_present=True,
            recovery_marker="tdlib_wait_code",
        )
        self.confirm_result = TdlibAuthResult(
            status=TdlibAuthStatus.READY,
            account_state=AccountState.AUTHORIZED_READY,
            runtime_health="ready",
            needs_code=False,
            session_present=True,
            telegram_user_id="777000",
            recovery_marker="tdlib_ready",
        )

    def start_otp(self, account_id: str, phone_number: str) -> TdlibAuthResult:
        self.started.append((account_id, phone_number))
        return self.start_result

    def confirm_otp(self, account_id: str, code: str) -> TdlibAuthResult:
        self.confirmed.append((account_id, code))
        return self.confirm_result

    def submit_password(self, account_id: str, password: str) -> TdlibAuthResult:
        self.passwords.append((account_id, password))
        return self.confirm_result


def test_auth_batch_validate_phones_reports_duplicates_existing_and_invalid() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        create_account(session, external_ref="+15550102000")

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.post(
        "/api/auth-batches/validate-phones",
        json={
            "items": [
                {"phone_number": "+1 (555) 010-2000"},
                {"phone_number": "+15550102000"},
                {"phone_number": "bad-phone"},
                {"phone_number": "+15550102001", "label": "new"},
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid_items"] == [{"phone_number": "+15550102001", "label": "new", "position": 3}]
    assert payload["duplicates"][0]["phone_number"] == "+15550102000"
    assert payload["existing_accounts"][0]["phone_number"] == "+15550102000"
    assert payload["invalid_items"][0]["input"] == "bad-phone"

    app.dependency_overrides.clear()


def test_auth_batch_create_is_idempotent_and_creates_pending_accounts() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    override_app_session(session_factory)
    client = TestClient(app)
    body = {
        "idempotency_key": "batch-key-1",
        "label": "April",
        "items": [{"phone_number": "+15550102000", "label": "a"}],
    }

    first = client.post("/api/auth-batches", json=body)
    second = client.post("/api/auth-batches", json=body)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["batch"]["id"] == second.json()["batch"]["id"]
    with session_factory() as session:
        batch = session.query(AuthBatch).one()
        item = session.query(AuthBatchItem).one()
        account = session.get(Account, item.account_id)
        assert batch.total_count == 1
        assert item.status == "queued"
        assert account is not None
        assert account.external_ref == "+15550102000"
        assert account.account_state == AccountState.REGISTERED

    app.dependency_overrides.clear()


def test_auth_batch_create_rejects_existing_only_batch_with_clear_details() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        create_account(session, external_ref="+15550102000")

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.post(
        "/api/auth-batches",
        json={"idempotency_key": "batch-existing-only", "items": [{"phone_number": "+15550102000"}]},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "AUTH_BATCH_EMPTY"
    assert payload["details"]["existing_accounts"][0]["phone_number"] == "+15550102000"
    with session_factory() as session:
        assert session.query(AuthBatch).count() == 0

    app.dependency_overrides.clear()


def test_auth_batch_validation_allows_stale_terminal_batch_account() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = Account(
            external_ref="+15550102000",
            auth_source="batch",
            account_state=AccountState.AWAITING_CODE,
        )
        account.runtime_state = AccountRuntimeState(
            session_present=True,
            runtime_health="awaiting_code",
            recovery_marker="tdlib_wait_code",
        )
        session.add(account)
        session.flush()
        batch = AuthBatch(idempotency_key="old-batch", status="completed", total_count=1, failed_count=1)
        session.add(batch)
        session.flush()
        session.add(
            AuthBatchItem(
                batch_id=batch.id,
                account_id=account.id,
                phone_number=account.external_ref,
                position=0,
                status="timed_out",
            )
        )
        session.commit()

        result = validate_batch_phones(session, [PhoneInput("+15550102000")])

    assert result["valid_items"] == [{"phone_number": "+15550102000", "label": None, "position": 0}]
    assert result["existing_accounts"] == []


def test_auth_batch_validation_reports_active_batch_conflict_before_existing_account() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = Account(
            external_ref="+15550102000",
            auth_source="batch",
            account_state=AccountState.AWAITING_CODE,
        )
        account.runtime_state = AccountRuntimeState(
            session_present=True,
            runtime_health="awaiting_code",
            recovery_marker="tdlib_wait_code",
        )
        session.add(account)
        session.flush()
        batch = AuthBatch(idempotency_key="active-batch", status="running", total_count=1)
        session.add(batch)
        session.flush()
        item = AuthBatchItem(
            batch_id=batch.id,
            account_id=account.id,
            phone_number=account.external_ref,
            position=0,
            status="waiting_code",
        )
        session.add(item)
        session.commit()

        result = validate_batch_phones(session, [PhoneInput("+15550102000")])

    assert result["valid_items"] == []
    assert result["existing_accounts"] == []
    assert result["active_batch_conflicts"][0]["phone_number"] == "+15550102000"
    assert result["active_batch_conflicts"][0]["batch_id"] == batch.id
    assert result["active_batch_conflicts"][0]["batch_item_id"] == item.id


def test_auth_batch_create_reuses_and_resets_stale_terminal_batch_account(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "tdlib_database_root", tmp_path / "database")
    monkeypatch.setattr(settings, "tdlib_files_root", tmp_path / "files")
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = Account(
            external_ref="+15550102000",
            auth_source="batch",
            account_state=AccountState.AWAITING_CODE,
        )
        account.runtime_state = AccountRuntimeState(
            session_present=True,
            runtime_health="awaiting_code",
            recovery_marker="tdlib_wait_code",
        )
        session.add(account)
        session.flush()
        (settings.tdlib_database_root / account.id).mkdir(parents=True)
        (settings.tdlib_database_root / account.id / "db.sqlite").write_text("stale")
        (settings.tdlib_files_root / account.id).mkdir(parents=True)
        batch = AuthBatch(idempotency_key="old-batch-reset", status="completed", total_count=1, failed_count=1)
        session.add(batch)
        session.flush()
        session.add(
            AuthBatchItem(
                batch_id=batch.id,
                account_id=account.id,
                phone_number=account.external_ref,
                position=0,
                status="timed_out",
            )
        )
        session.commit()
        account_id = account.id

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.post(
        "/api/auth-batches",
        json={"idempotency_key": "batch-reuse-stale", "items": [{"phone_number": "+15550102000"}]},
    )

    assert response.status_code == 201
    with session_factory() as session:
        items = session.query(AuthBatchItem).filter(AuthBatchItem.account_id == account_id).all()
        account = session.get(Account, account_id)
        assert len(items) == 2
        assert account.account_state == AccountState.REGISTERED
        assert account.runtime_state.session_present is False
        assert account.runtime_state.runtime_health == "unknown"
        assert account.runtime_state.recovery_marker is None
    assert (settings.tdlib_database_root / account_id / "db.sqlite").exists()
    assert (settings.tdlib_files_root / account_id).exists()

    app.dependency_overrides.clear()


def test_auth_batch_start_dispatches_item_and_worker_moves_to_waiting_code(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    enqueued: list[str] = []
    monkeypatch.setattr("app.services.auth_batch_dispatcher.enqueue_batch_start_auth", lambda item_id, attempt_count, delay_seconds=0: enqueued.append(item_id) or True)
    adapter = BatchFakeAuthAdapter()
    monkeypatch.setattr("app.services.auth_batch_tdlib.build_tdlib_auth_adapter", lambda: adapter)

    override_app_session(session_factory)
    client = TestClient(app)
    created = client.post(
        "/api/auth-batches",
        json={"idempotency_key": "batch-key-2", "items": [{"phone_number": "+15550102000"}]},
    ).json()
    batch_id = created["batch"]["id"]

    start = client.post(f"/api/auth-batches/{batch_id}/start")

    assert start.status_code == 200
    assert len(enqueued) == 1
    from app.workers.auth_batch_jobs import run_batch_start_auth

    run_batch_start_auth(enqueued[0], session_factory=session_factory)
    with session_factory() as session:
        item = session.get(AuthBatchItem, enqueued[0])
        assert item is not None
        assert item.status == "waiting_code"
        assert item.code_expires_at is not None

    app.dependency_overrides.clear()


def test_auth_batch_start_returns_503_when_queue_enqueue_fails(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    monkeypatch.setattr("app.services.auth_batch_dispatcher.enqueue_batch_start_auth", lambda item_id, attempt_count, delay_seconds=0: False)

    override_app_session(session_factory)
    client = TestClient(app)
    created = client.post(
        "/api/auth-batches",
        json={
            "idempotency_key": "batch-key-queue-down",
            "items": [{"phone_number": "+15550102000"}, {"phone_number": "+15550102001"}],
        },
    ).json()
    batch_id = created["batch"]["id"]

    response = client.post(f"/api/auth-batches/{batch_id}/start")

    assert response.status_code == 503
    assert response.json()["error_code"] == "QUEUE_UNAVAILABLE"
    with session_factory() as session:
        batch = session.get(AuthBatch, batch_id)
        items = session.query(AuthBatchItem).filter(AuthBatchItem.batch_id == batch_id).all()
        assert batch is not None
        assert batch.status == "failed"
        assert {item.status for item in items} == {"failed"}
        assert {item.error_code for item in items} == {"QUEUE_UNAVAILABLE"}

    app.dependency_overrides.clear()


def test_auth_batch_partial_enqueue_failure_does_not_fail_launched_item(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    calls = 0

    def flaky_enqueue(item_id: str, attempt_count: int, delay_seconds: int = 0) -> bool:
        nonlocal calls
        calls += 1
        return calls == 1

    monkeypatch.setattr("app.services.auth_batch_dispatcher.enqueue_batch_start_auth", flaky_enqueue)

    override_app_session(session_factory)
    client = TestClient(app)
    created = client.post(
        "/api/auth-batches",
        json={
            "idempotency_key": "batch-key-partial-queue-down",
            "items": [{"phone_number": "+15550102000"}, {"phone_number": "+15550102001"}],
        },
    ).json()
    batch_id = created["batch"]["id"]

    response = client.post(f"/api/auth-batches/{batch_id}/start")

    assert response.status_code == 200
    with session_factory() as session:
        items = session.query(AuthBatchItem).filter(AuthBatchItem.batch_id == batch_id).order_by(AuthBatchItem.position).all()
        assert [item.status for item in items] == ["starting", "failed"]
        assert items[0].error_code is None
        assert items[1].error_code == "QUEUE_UNAVAILABLE"

    app.dependency_overrides.clear()


def test_auth_batch_retry_rejects_terminal_batch_item() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        batch = AuthBatch(idempotency_key="batch-key-terminal-retry", status="failed", total_count=1, failed_count=1)
        session.add(batch)
        session.flush()
        item = AuthBatchItem(
            batch_id=batch.id,
            account_id=account.id,
            phone_number=account.external_ref,
            position=0,
            status="failed",
            error_code="QUEUE_UNAVAILABLE",
        )
        session.add(item)
        session.commit()
        batch_id = batch.id
        item_id = item.id

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.post(f"/api/auth-batches/{batch_id}/items/{item_id}/retry")

    assert response.status_code == 409
    with session_factory() as session:
        item = session.get(AuthBatchItem, item_id)
        assert item is not None
        assert item.status == "failed"

    app.dependency_overrides.clear()


def test_auth_batch_dispatches_multiple_items_without_scheduler_delay(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    enqueued: list[tuple[str, int]] = []

    def fake_enqueue(item_id: str, attempt_count: int, delay_seconds: int = 0) -> bool:
        enqueued.append((item_id, delay_seconds))
        return True

    monkeypatch.setattr("app.services.auth_batch_dispatcher.enqueue_batch_start_auth", fake_enqueue)

    override_app_session(session_factory)
    client = TestClient(app)
    created = client.post(
        "/api/auth-batches",
        json={
            "idempotency_key": "batch-key-no-delay",
            "items": [{"phone_number": "+15550102000"}, {"phone_number": "+15550102001"}],
        },
    ).json()
    batch_id = created["batch"]["id"]

    start = client.post(f"/api/auth-batches/{batch_id}/start")

    assert start.status_code == 200
    assert len(enqueued) == 2
    assert [delay for _, delay in enqueued] == [0, 0]

    app.dependency_overrides.clear()


def test_auth_batch_submit_code_authorizes_without_persisting_secret(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    adapter = BatchFakeAuthAdapter()
    monkeypatch.setattr("app.services.auth_batch_tdlib.build_tdlib_auth_adapter", lambda: adapter)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        batch = AuthBatch(idempotency_key="batch-key-3", label="Codes", status="running", total_count=1)
        session.add(batch)
        session.flush()
        item = AuthBatchItem(
            batch_id=batch.id,
            account_id=account.id,
            phone_number=account.external_ref,
            position=0,
            status="waiting_code",
            code_expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        session.add(item)
        session.commit()
        batch_id = batch.id
        item_id = item.id

    override_app_session(session_factory)
    client = TestClient(app)
    response = client.post(
        f"/api/auth-batches/{batch_id}/items/{item_id}/submit-code",
        json={"code": "999888", "idempotency_key": "code-key-1"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "authorized"
    assert adapter.confirmed == [(response.json()["account_id"], "999888")]
    with session_factory() as session:
        item = session.get(AuthBatchItem, item_id)
        account = session.get(Account, item.account_id)
        assert item.status == "authorized"
        assert account.account_state == AccountState.AUTHORIZED_READY
        persisted_events = session.query(AuthBatchEvent).all()
        assert "999888" not in str([event.payload_json for event in persisted_events])

    app.dependency_overrides.clear()
