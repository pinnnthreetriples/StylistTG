from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from freezegun import freeze_time

from app.adapters.tdlib_auth import TdlibAuthResult, TdlibAuthStatus
from app.config import settings
from app.db import Base
from app.main import app
from app.models import (
    Account,
    AccountRuntimeState,
    AccountState,
    AuthBatch,
    AuthBatchEvent,
    AuthBatchItem,
    IdempotencyKey,
)
from app.services.accounts import create_account
from app.services.auth_batches import (
    PhoneInput,
    create_auth_batch,
    get_idempotency_result,
    save_idempotency_result,
    validate_batch_phones,
)
from app.services.database import create_sqlite_test_session_factory
from app.services.phone_hints import phone_hint, required_phone_hint

from conftest import FakeTdlibAuthAdapter, override_app_session


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Guarantee dependency_overrides are cleaned up after every test."""
    yield
    app.dependency_overrides.clear()


def _batch_adapter() -> FakeTdlibAuthAdapter:
    """Create a FakeTdlibAuthAdapter with batch-specific telegram_user_id."""
    adapter = FakeTdlibAuthAdapter()
    adapter.confirm_result = TdlibAuthResult(
        status=TdlibAuthStatus.READY,
        account_state=AccountState.AUTHORIZED_READY,
        runtime_health="ready",
        needs_code=False,
        session_present=True,
        telegram_user_id="777000",
        recovery_marker="tdlib_ready",
    )
    return adapter


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
    assert payload["valid_items"] == [
        {"phone_number": "+15550102001", "label": "new", "position": 3}
    ]
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
        json={
            "idempotency_key": "batch-existing-only",
            "items": [{"phone_number": "+15550102000"}],
        },
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
        batch = AuthBatch(
            idempotency_key="old-batch", status="completed", total_count=1, failed_count=1
        )
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


def test_auth_batch_create_reuses_and_resets_stale_terminal_batch_account(
    tmp_path, monkeypatch
) -> None:
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
        batch = AuthBatch(
            idempotency_key="old-batch-reset", status="completed", total_count=1, failed_count=1
        )
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
    monkeypatch.setattr(
        "app.services.auth_batch_dispatcher.enqueue_batch_start_auth",
        lambda item_id, attempt_count, delay_seconds=0: enqueued.append(item_id) or True,
    )
    adapter = _batch_adapter()
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
    monkeypatch.setattr(
        "app.services.auth_batch_dispatcher.enqueue_batch_start_auth",
        lambda item_id, attempt_count, delay_seconds=0: False,
    )

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

    monkeypatch.setattr(
        "app.services.auth_batch_dispatcher.enqueue_batch_start_auth", flaky_enqueue
    )

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
        items = (
            session.query(AuthBatchItem)
            .filter(AuthBatchItem.batch_id == batch_id)
            .order_by(AuthBatchItem.position)
            .all()
        )
        assert [item.status for item in items] == ["starting", "failed"]
        assert items[0].error_code is None
        assert items[1].error_code == "QUEUE_UNAVAILABLE"

    app.dependency_overrides.clear()


def test_auth_batch_retry_rejects_terminal_batch_item() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        batch = AuthBatch(
            idempotency_key="batch-key-terminal-retry",
            status="failed",
            total_count=1,
            failed_count=1,
        )
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


def test_auth_batch_retry_clears_terminal_item_counter(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    monkeypatch.setattr("app.api.auth_batches.dispatch_once", lambda session, batch_id: 0)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102002")
        batch = AuthBatch(
            idempotency_key="batch-key-retry-counter",
            status="running",
            total_count=1,
            failed_count=1,
        )
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

    assert response.status_code == 200
    with session_factory() as session:
        batch = session.get(AuthBatch, batch_id)
        item = session.get(AuthBatchItem, item_id)
        assert batch is not None
        assert item is not None
        assert item.status == "queued"
        assert batch.failed_count == 0
        assert batch.success_count == 0

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


def test_auth_batch_submit_code_updates_item_without_persisting_code(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    adapter = _batch_adapter()
    monkeypatch.setattr("app.services.auth_batch_tdlib.build_tdlib_auth_adapter", lambda: adapter)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        batch = AuthBatch(
            idempotency_key="batch-key-3", label="Codes", status="running", total_count=1
        )
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


def test_submit_code_idempotency_key_is_scoped_to_item(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    adapter = _batch_adapter()
    monkeypatch.setattr("app.services.auth_batch_tdlib.build_tdlib_auth_adapter", lambda: adapter)

    with session_factory() as session:
        account_one = create_account(session, external_ref="+15550102010")
        account_two = create_account(session, external_ref="+15550102011")
        batch = AuthBatch(
            idempotency_key="batch-key-idempotency-scope",
            label="Codes",
            status="running",
            total_count=2,
        )
        session.add(batch)
        session.flush()
        item_one = AuthBatchItem(
            batch_id=batch.id,
            account_id=account_one.id,
            phone_number=account_one.external_ref,
            position=0,
            status="waiting_code",
            code_expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        item_two = AuthBatchItem(
            batch_id=batch.id,
            account_id=account_two.id,
            phone_number=account_two.external_ref,
            position=1,
            status="waiting_code",
            code_expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        session.add_all([item_one, item_two])
        session.commit()
        batch_id = batch.id
        item_one_id = item_one.id
        item_two_id = item_two.id

    override_app_session(session_factory)
    client = TestClient(app)
    try:
        first = client.post(
            f"/api/auth-batches/{batch_id}/items/{item_one_id}/submit-code",
            json={"code": "111111", "idempotency_key": "shared-code-key"},
        )
        second = client.post(
            f"/api/auth-batches/{batch_id}/items/{item_two_id}/submit-code",
            json={"code": "222222", "idempotency_key": "shared-code-key"},
        )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 409
    assert first.json()["id"] == item_one_id
    assert second.json()["error_code"] == "AUTH_BATCH_STATE_CONFLICT"
    assert adapter.confirmed == [(first.json()["account_id"], "111111")]


@freeze_time("2026-01-15 12:00:00")
def test_idempotency_result_allows_expired_key_reuse() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        session.add(
            IdempotencyKey(
                key="expired-code-key",
                operation="submit_code",
                entity_id="entity-one",
                response_json={"status": "old"},
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
        )
        session.commit()

        assert (
            get_idempotency_result(
                session,
                key="expired-code-key",
                operation="submit_code",
                entity_id="entity-one",
            )
            is None
        )
        save_idempotency_result(
            session,
            key="expired-code-key",
            operation="submit_code",
            entity_id="entity-one",
            response_json={"status": "new"},
        )
        session.commit()

        assert get_idempotency_result(
            session,
            key="expired-code-key",
            operation="submit_code",
            entity_id="entity-one",
        ) == {"status": "new"}


def test_idempotency_result_rejects_operation_and_entity_mismatch() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        save_idempotency_result(
            session,
            key="shared-idempotency-key",
            operation="submit_code",
            entity_id="entity-one",
            response_json={"status": "ok"},
        )
        session.commit()

        with pytest.raises(ValueError, match="another operation"):
            get_idempotency_result(
                session,
                key="shared-idempotency-key",
                operation="submit_2fa",
                entity_id="entity-one",
            )

        with pytest.raises(ValueError, match="another entity"):
            get_idempotency_result(
                session,
                key="shared-idempotency-key",
                operation="submit_code",
                entity_id="entity-two",
            )


def test_submit_code_expired_idempotency_key_allows_new_submission(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    adapter = _batch_adapter()
    monkeypatch.setattr("app.services.auth_batch_tdlib.build_tdlib_auth_adapter", lambda: adapter)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102020")
        batch = AuthBatch(
            idempotency_key="batch-key-expired-http", label="Codes", status="running", total_count=1
        )
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
        session.flush()
        session.add(
            IdempotencyKey(
                key="expired-http-key",
                operation="submit_code",
                entity_id=item.id,
                response_json={"status": "old"},
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
        )
        session.commit()
        batch_id = batch.id
        item_id = item.id

    override_app_session(session_factory)
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/auth-batches/{batch_id}/items/{item_id}/submit-code",
            json={"code": "555555", "idempotency_key": "expired-http-key"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "authorized"
    assert adapter.confirmed == [(response.json()["account_id"], "555555")]


def test_submit_2fa_idempotency_key_scoped_to_item(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    adapter = _batch_adapter()
    monkeypatch.setattr("app.services.auth_batch_tdlib.build_tdlib_auth_adapter", lambda: adapter)

    with session_factory() as session:
        account_one = create_account(session, external_ref="+15550102030")
        account_two = create_account(session, external_ref="+15550102031")
        batch = AuthBatch(
            idempotency_key="batch-key-2fa-scope", label="2FA", status="running", total_count=2
        )
        session.add(batch)
        session.flush()
        item_one = AuthBatchItem(
            batch_id=batch.id,
            account_id=account_one.id,
            phone_number=account_one.external_ref,
            position=0,
            status="waiting_2fa",
        )
        item_two = AuthBatchItem(
            batch_id=batch.id,
            account_id=account_two.id,
            phone_number=account_two.external_ref,
            position=1,
            status="waiting_2fa",
        )
        session.add_all([item_one, item_two])
        session.commit()
        batch_id = batch.id
        item_one_id = item_one.id
        item_two_id = item_two.id

    override_app_session(session_factory)
    client = TestClient(app)
    try:
        first = client.post(
            f"/api/auth-batches/{batch_id}/items/{item_one_id}/submit-2fa",
            json={"password": "pass1", "idempotency_key": "shared-2fa-key"},
        )
        second = client.post(
            f"/api/auth-batches/{batch_id}/items/{item_two_id}/submit-2fa",
            json={"password": "pass2", "idempotency_key": "shared-2fa-key"},
        )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 409
    assert first.json()["id"] == item_one_id
    assert second.json()["error_code"] == "AUTH_BATCH_STATE_CONFLICT"
    assert adapter.passwords == [(first.json()["account_id"], "pass1")]


def test_submit_code_operation_mismatch_returns_generic_409(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    adapter = _batch_adapter()
    monkeypatch.setattr("app.services.auth_batch_tdlib.build_tdlib_auth_adapter", lambda: adapter)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102040")
        batch = AuthBatch(
            idempotency_key="batch-key-op-mismatch", label="Codes", status="running", total_count=1
        )
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
        session.flush()
        save_idempotency_result(
            session,
            key="op-mismatch-key",
            operation="submit_2fa",
            entity_id=item.id,
            response_json={"status": "ok"},
        )
        session.commit()
        batch_id = batch.id
        item_id = item.id

    override_app_session(session_factory)
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/auth-batches/{batch_id}/items/{item_id}/submit-code",
            json={"code": "123456", "idempotency_key": "op-mismatch-key"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error_code"] == "AUTH_BATCH_STATE_CONFLICT"
    assert len(adapter.confirmed) == 0


def test_auth_batch_item_read_uses_phone_hint() -> None:
    from app.models import DEFAULT_LOCAL_WORKSPACE_ID
    from app.services.auth_context import AuthContext, get_current_auth_context

    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        batch, _ = create_auth_batch(
            session,
            idempotency_key="batch-hint-integration",
            label="hint",
            inputs=[PhoneInput(phone_number="+15550102050")],
        )
        session.commit()
        batch_id = batch.id

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="viewer-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="viewer",
        auth_source="test",
    )
    try:
        response = TestClient(app).get(f"/api/auth-batches/{batch_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["phone_hint"] == "***2050"
    assert item["phone_number"] is None


def test_phone_hint_helper_masks_consistently() -> None:
    assert phone_hint("+1 (555) 010-2000") == "***2000"
    assert phone_hint("123") == "***"
    assert phone_hint("") is None
    assert phone_hint(None) is None
    assert required_phone_hint("") == "***"
