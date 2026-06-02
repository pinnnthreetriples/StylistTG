from __future__ import annotations

# test-analyzer: disable-file=TQA050 reason="bare response.json() truthiness check; replaced with exact body assertion in the #263 sweep" issue="#263" expires="2026-08-31"

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from freezegun import freeze_time

from app.db import Base
from app.main import app
from app.models import (
    AccountState,
    AccountProfileState,
    AccountProfileAudioState,
    AccountStoryPost,
    Job,
    JobState,
    JobStepResult,
    StepStatus,
)
from app.services.accounts import create_account
from app.services.database import create_sqlite_test_session_factory

from conftest import (
    FakeExecutionUsableAdapter,
    FakeProfileSyncAdapter,
    override_app_session,
    seed_asset,
    seed_job,
)
from tests.helpers.app import app_client
from tests.helpers.factories import make_session


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Guarantee dependency_overrides are cleaned up after every test."""
    yield
    app.dependency_overrides.clear()


# test-analyzer: disable=TQA004 reason="aggregated payload contract test — verifies many fields in single response"
def test_dashboard_profile_returns_aggregated_payload(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        account.account_state = AccountState.EXECUTION_USABLE
        account.telegram_user_id = "777000"
        account.runtime_state.runtime_health = "ready"
        account.runtime_state.reauth_required = False
        account.runtime_state.authorized_last_confirmed_at = datetime.now(UTC)
        account.profile_state = AccountProfileState(
            telegram_user_id="777000",
            first_name="King",
            last_name="Blackburn",
            username="kingblackburn",
            bio="Live from Telegram",
        )
        account.profile_audio_state = AccountProfileAudioState(
            telegram_file_id="tg-file-1",
            title="Theme",
            performer="Stylist",
            duration_seconds=42,
            mime="audio/mpeg",
            source_asset_id="audio-1",
        )
        asset = seed_asset(session)
        payload = {
            "name": "Alice Example",
            "bio": "Profile editor",
            "username": "alice_example",
            "photo_asset_id": asset.id,
        }
        job = seed_job(
            session,
            account_id=account.id,
            payload=payload,
            state=JobState.COMPLETED,
            finished_at=datetime.now(UTC),
        )
        step = JobStepResult(
            job_id=job.id,
            step_key="set_username",
            step_type="set_username",
            status=StepStatus.FAILED,
            error_code="USERNAME_INVALID",
            error_class="validation",
            finished_at=datetime.now(UTC),
        )
        photo_step = JobStepResult(
            job_id=job.id,
            step_key="set_profile_photo",
            step_type="set_profile_photo",
            status=StepStatus.SUCCEEDED,
            result_payload_json={"applied": {"photo_asset_id": asset.id}},
            finished_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        session.add_all([step, photo_step])
        session.commit()
        account_id = account.id

    override_app_session(session_factory)
    monkeypatch.setattr(
        "app.modules.account_shared.runtime.build_profile_execution_adapter",
        lambda: FakeExecutionUsableAdapter(ok=True),
    )
    client = TestClient(app)

    response = client.get(f"/api/dashboard/profile/{account_id}")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {
        "account",
        "current_profile",
        "profile_audio",
        "story_posts",
        "editable_fields",
        "pipeline",
        "diagnostics",
    }
    assert payload["account"] == {
        "account_id": account_id,
        "display_name": "King Blackburn",
        "username": "kingblackburn",
        "phone_number": "+15550102000",
        "telegram_user_id": "777000",
        "account_state": "execution_usable",
        "runtime_health": "ready",
        "reauth_required": False,
        "is_execution_usable": True,
    }
    assert payload["current_profile"] == {
        "first_name": "King",
        "last_name": "Blackburn",
        "bio": "Live from Telegram",
        "username": "kingblackburn",
        "profile_photo_asset_id": "asset-1",
    }
    assert payload["profile_audio"] == {
        "telegram_file_id": "tg-file-1",
        "title": "Theme",
        "performer": "Stylist",
        "duration_seconds": 42,
        "mime": "audio/mpeg",
        "source_asset_id": "audio-1",
    }
    assert payload["story_posts"] == []
    assert payload["editable_fields"] == {
        "name": "King Blackburn",
        "bio": "Live from Telegram",
        "username": "kingblackburn",
        "profile_photo": "asset-1",
    }
    assert payload["pipeline"]["latest_job_id"] == "job-1"
    assert payload["pipeline"]["latest_job_state"] == "completed"
    assert payload["pipeline"]["has_active_job"] is False
    assert payload["pipeline"]["unsaved_changes_supported"] is True
    assert payload["diagnostics"]["last_error_code"] == "USERNAME_INVALID"
    assert payload["diagnostics"]["last_error_class"] == "validation"
    assert payload["diagnostics"]["real_execution_enabled"] is False
    assert payload["diagnostics"]["stories_live_execution_enabled"] is False

    app.dependency_overrides.clear()


@freeze_time("2026-01-15 12:00:00")
def test_accounts_list_returns_profile_summary() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        account.account_state = AccountState.EXECUTION_USABLE
        account.telegram_user_id = "777000"
        account.runtime_state.runtime_health = "ready"
        account.profile_state = AccountProfileState(
            telegram_user_id="777000",
            first_name="Marina",
            last_name="Manina",
            username="kkk4n44",
            bio="Profile editor",
        )
        asset = seed_asset(session)
        job = seed_job(
            session,
            account_id=account.id,
            payload={"photo_asset_id": asset.id},
            state=JobState.COMPLETED,
            finished_at=datetime.now(UTC),
        )
        session.add(
            JobStepResult(
                job_id=job.id,
                step_key="set_profile_photo",
                step_type="set_profile_photo",
                status=StepStatus.SUCCEEDED,
                result_payload_json={"applied": {"photo_asset_id": asset.id}},
                finished_at=datetime.now(UTC),
            ),
        )
        session.commit()
        account_id = account.id

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.get("/api/accounts")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0] == {
        "account_id": account_id,
        "display_name": "Marina Manina",
        "username": "kkk4n44",
        "phone_number": "+15550102000",
        "telegram_user_id": "777000",
        "origin": "imported",
        "account_state": "execution_usable",
        "terminal_status": "none",
        "runtime_health": "ready",
        "is_execution_usable": True,
        "is_test_dc": False,
        "profile_photo_asset_id": "asset-1",
        "updated_at": payload[0]["updated_at"],
        "warmup": None,
    }
    assert payload[0]["updated_at"]

    app.dependency_overrides.clear()


def test_accounts_list_marks_test_dc_accounts() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        create_account(session, external_ref="+9996611234", telegram_user_id="mock-user")
        session.commit()

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.get("/api/accounts")

    assert response.status_code == 200
    assert response.json()[0]["is_test_dc"] is True

    app.dependency_overrides.clear()


def test_account_delete_requires_lifecycle_request_with_terminal_jobs() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        job = seed_job(session, account_id=account.id, payload={}, state=JobState.COMPLETED)
        account_id = account.id
        job_id = job.id

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.delete(f"/api/accounts/{account_id}")

    assert response.status_code == 409
    assert response.json()["error_code"] == "ACCOUNT_DELETE_REQUIRES_REQUEST"
    with session_factory() as session:
        assert session.get(Job, job_id) is not None
        assert session.get(type(account), account_id) is not None

    app.dependency_overrides.clear()


def test_account_delete_requires_lifecycle_request_before_active_job_check() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        seed_job(session, account_id=account.id, payload={}, state=JobState.RUNNING)
        account_id = account.id

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.delete(f"/api/accounts/{account_id}")

    assert response.status_code == 409
    assert response.json()["error_code"] == "ACCOUNT_DELETE_REQUIRES_REQUEST"

    app.dependency_overrides.clear()


def test_account_delete_does_not_reap_stale_jobs_in_legacy_endpoint(monkeypatch) -> None:
    monkeypatch.setattr("app.services.accounts.settings.stale_job_timeout_seconds", 300)
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        job = seed_job(
            session,
            account_id=account.id,
            payload={},
            state=JobState.QUEUED,
        )
        job.queued_at = datetime.now(UTC) - timedelta(minutes=10)
        session.commit()
        account_id = account.id
        job_id = job.id

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.delete(f"/api/accounts/{account_id}")

    assert response.status_code == 409
    assert response.json()["error_code"] == "ACCOUNT_DELETE_REQUIRES_REQUEST"
    with session_factory() as session:
        assert session.get(Job, job_id) is not None
        assert session.get(type(account), account_id) is not None

    app.dependency_overrides.clear()


def test_execution_policy_settings_can_update_profile_job_cooldown(monkeypatch) -> None:
    from app.config import settings as api_settings

    monkeypatch.setattr(api_settings, "profile_job_cooldown_seconds", 120)
    session_factory, _engine = make_session()

    with app_client(session_factory, role="admin") as client:
        response = client.get("/api/settings/execution-policy")

        assert response.status_code == 200
        payload = response.json()
        _assert_default_execution_policy_payload(payload)

        patch_response = client.patch(
            "/api/settings/execution-policy",
            json={"profile_job_cooldown_seconds": 0},
        )

        assert patch_response.status_code == 200
        assert patch_response.json()["profile_job_cooldown_seconds"] == 0
        assert patch_response.json()["profile_job_cooldown_enabled"] is False

        repeat_get_response = client.get("/api/settings/execution-policy")
        assert repeat_get_response.status_code == 200
        assert repeat_get_response.json()["profile_job_cooldown_seconds"] == 0

    assert api_settings.profile_job_cooldown_seconds == 120


def _assert_default_execution_policy_payload(payload: dict) -> None:
    assert payload["profile_job_cooldown_seconds"] == 120
    assert payload["profile_job_cooldown_enabled"] is True
    assert payload["allowed_profile_job_cooldown_seconds"] == [30, 60, 120, 300, 600]
    assert "username_cooldown_seconds" in payload
    assert "unknown_capability_policy" in payload
    assert "non_overridable_blockers" in payload


def test_execution_policy_rejects_too_small_nonzero_cooldown(monkeypatch) -> None:
    from app.config import settings as api_settings

    monkeypatch.setattr(api_settings, "profile_job_cooldown_seconds", 120)
    session_factory, _engine = make_session()

    with app_client(session_factory, role="admin") as client:
        response = client.patch(
            "/api/settings/execution-policy",
            json={"profile_job_cooldown_seconds": 10},
        )

    assert response.status_code == 422
    assert response.json()


def test_profile_preview_returns_validation_plan_and_dedup(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        account.account_state = AccountState.EXECUTION_USABLE
        account.runtime_state.runtime_health = "ready"
        asset = seed_asset(session)
        preview_payload = {
            "name": "Alice Example",
            "bio": "Profile editor",
            "username": "alice_example",
            "photo_asset_id": asset.id,
        }
        seed_job(session, account_id=account.id, payload=preview_payload, state=JobState.QUEUED)
        account_id = account.id
        before_count = session.query(Job).count()

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.post(
        "/api/jobs/profile/preview",
        json={"account_id": account_id, **preview_payload},
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {
        "can_create_job",
        "blocking_errors",
        "warnings",
        "normalized_payload",
        "execution_intent_hash",
        "plan_json_snapshot",
        "steps",
        "requires_execution_usable",
        "dedup_would_block",
        "dedup_blocked_by_job_id",
    }
    assert payload["can_create_job"] is True
    assert payload["blocking_errors"] == []
    assert payload["warnings"] == []
    assert payload["normalized_payload"]["photo_asset_id"] == "asset-1"
    photo_asset_path = payload["normalized_payload"]["photo_asset_path"].replace("\\", "/")
    assert photo_asset_path.endswith("assets/normalized/profile.jpg")
    assert [step["step_key"] for step in payload["steps"]] == [
        "set_name",
        "set_bio",
        "set_username",
        "set_profile_photo",
    ]
    assert payload["requires_execution_usable"] is True
    assert payload["dedup_would_block"] is True
    assert payload["dedup_blocked_by_job_id"] == "job-1"

    with session_factory() as session:
        assert session.query(Job).count() == before_count

    app.dependency_overrides.clear()


def test_profile_job_create_success_and_latest_job_contract(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        account.account_state = AccountState.AUTHORIZED_READY
        asset = seed_asset(session)
        account_id = account.id

    override_app_session(session_factory)
    monkeypatch.setattr(
        "app.api.jobs.build_profile_execution_adapter",
        lambda: FakeExecutionUsableAdapter(ok=True),
    )
    monkeypatch.setattr("app.api.jobs.enqueue_profile_job", lambda job_id: None)
    client = TestClient(app)

    response = client.post(
        "/api/jobs/profile",
        json={
            "account_id": account_id,
            "name": "Alice Example",
            "bio": "Profile editor",
            "username": "alice_example",
            "photo_asset_id": asset.id,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert set(payload.keys()) == {
        "job_id",
        "job_state",
        "execution_intent_hash",
        "plan_summary",
        "created_at",
        "dedup_blocked_by_job_id",
        "message",
    }
    assert payload["job_state"] == "queued"
    assert payload["dedup_blocked_by_job_id"] is None

    latest = client.get(f"/api/accounts/{account_id}/jobs/latest")
    assert latest.status_code == 200
    assert latest.json()["job_id"] == payload["job_id"]
    assert latest.json()["job_state"] == "queued"

    jobs_response = client.get(f"/api/accounts/{account_id}/jobs?limit=10")
    assert jobs_response.status_code == 200
    assert len(jobs_response.json()) == 1
    assert jobs_response.json()[0]["job_id"] == payload["job_id"]

    app.dependency_overrides.clear()


def test_profile_job_create_returns_503_when_queue_enqueue_fails(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        account.account_state = AccountState.AUTHORIZED_READY
        account_id = account.id

    override_app_session(session_factory)
    monkeypatch.setattr(
        "app.api.jobs.build_profile_execution_adapter",
        lambda: FakeExecutionUsableAdapter(ok=True),
    )
    monkeypatch.setattr("app.api.jobs.enqueue_profile_job", lambda job_id: False)
    client = TestClient(app)

    response = client.post(
        "/api/jobs/profile",
        json={
            "account_id": account_id,
            "name": "Alice Example",
            "bio": "Profile editor",
            "username": "alice_example",
            "photo_asset_id": None,
        },
    )

    assert response.status_code == 503
    assert response.json()["error_code"] == "QUEUE_UNAVAILABLE"

    with session_factory() as session:
        job = session.query(Job).one()
        assert job.job_state == JobState.FAILED
        assert job.failure_reason == "enqueue_failed"

    app.dependency_overrides.clear()


def test_profile_job_create_returns_dedup_blocked_payload(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        account.account_state = AccountState.EXECUTION_USABLE
        asset = seed_asset(session)
        request_payload = {
            "name": "Alice Example",
            "bio": "Profile editor",
            "username": "alice_example",
            "photo_asset_id": asset.id,
        }
        seed_job(
            session,
            account_id=account.id,
            payload=request_payload,
            state=JobState.QUEUED,
            job_id="existing-job",
        )
        account_id = account.id

    override_app_session(session_factory)
    monkeypatch.setattr(
        "app.api.jobs.build_profile_execution_adapter",
        lambda: FakeExecutionUsableAdapter(ok=True),
    )
    monkeypatch.setattr("app.api.jobs.enqueue_profile_job", lambda job_id: None)
    client = TestClient(app)

    response = client.post("/api/jobs/profile", json={"account_id": account_id, **request_payload})

    assert response.status_code == 201
    payload = response.json()
    assert payload["job_state"] == "dedup_blocked"
    assert payload["dedup_blocked_by_job_id"] == "existing-job"
    assert payload["message"] == "job deduplicated by active execution intent"

    app.dependency_overrides.clear()


@freeze_time("2026-01-15 12:00:00")
# test-analyzer: disable=TQA004 reason="polling contract test — verifies job/step fields needed by dashboard"
def test_job_details_and_steps_are_polling_friendly() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        account.account_state = AccountState.EXECUTION_USABLE
        job = seed_job(
            session,
            account_id=account.id,
            payload={
                "name": "Alice Example",
                "bio": "Profile editor",
                "username": "alice_example",
                "photo_asset_id": "asset-1",
            },
            state=JobState.PARTIALLY_COMPLETED,
            finished_at=datetime.now(UTC),
            failure_reason="partial uncertainty",
        )
        session.add_all(
            [
                JobStepResult(
                    job_id=job.id,
                    step_key="set_username",
                    step_type="set_username",
                    status=StepStatus.UNCERTAIN,
                    verification_attempted=True,
                    verification_result={"matched": False},
                    uncertain_reason="verify mismatch",
                    error_code="USERNAME_AMBIGUOUS",
                    error_class="verification",
                    started_at=datetime(2026, 1, 1, tzinfo=UTC),
                    finished_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
                ),
                JobStepResult(
                    job_id=job.id,
                    step_key="set_name",
                    step_type="set_name",
                    status=StepStatus.SUCCEEDED,
                    verification_attempted=False,
                    verification_result=None,
                    started_at=datetime(2026, 1, 1, 0, 0, 2, tzinfo=UTC),
                    finished_at=datetime(2026, 1, 1, 0, 0, 3, tzinfo=UTC),
                ),
            ]
        )
        session.commit()
        account_id = account.id
        job_id = job.id

    override_app_session(session_factory)
    client = TestClient(app)

    job_response = client.get(f"/api/jobs/{job_id}")
    assert job_response.status_code == 200
    job_payload = job_response.json()
    assert set(job_payload.keys()) == {
        "job_id",
        "job_state",
        "account_id",
        "execution_intent_hash",
        "started_at",
        "finished_at",
        "failure_reason",
        "can_retry",
        "can_refresh_runtime",
        "step_counts",
    }
    assert job_payload["job_state"] == "partially_completed"
    assert job_payload["can_retry"] is False
    assert job_payload["can_refresh_runtime"] is True
    assert job_payload["step_counts"] == {
        "planned": 2,
        "started": 0,
        "succeeded": 1,
        "failed": 0,
        "uncertain": 1,
        "skipped": 0,
    }

    steps_response = client.get(f"/api/jobs/{job_id}/steps")
    assert steps_response.status_code == 200
    steps_payload = steps_response.json()
    assert [step["step_key"] for step in steps_payload] == ["set_name", "set_username"]
    assert set(steps_payload[0].keys()) == {
        "step_key",
        "step_type",
        "status",
        "verification_attempted",
        "verification_result",
        "uncertain_reason",
        "error_code",
        "error_class",
        "result_payload_json",
        "started_at",
        "finished_at",
    }
    assert steps_payload[1]["uncertain_reason"] == "verify mismatch"
    assert steps_payload[1]["error_code"] == "USERNAME_AMBIGUOUS"
    assert steps_payload[1]["error_class"] == "verification"

    latest = client.get(f"/api/accounts/{account_id}/jobs/latest")
    assert latest.status_code == 200
    assert latest.json()["job_id"] == job_id

    app.dependency_overrides.clear()


def test_job_cancel_marks_waiting_job_canceled(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        job = seed_job(
            session,
            account_id=account.id,
            payload={"name": "Cancel Me"},
            state=JobState.WAITING_LOCK,
        )
        job_id = job.id
        session.commit()

    removed: list[str] = []
    monkeypatch.setattr(
        "app.api.jobs.remove_job_from_queue",
        lambda next_job_id: removed.append(next_job_id) or True,
    )
    override_app_session(session_factory)
    client = TestClient(app)

    response = client.post(f"/api/jobs/{job_id}/cancel")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_state"] == "canceled"
    assert removed == [job_id]
    with session_factory() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.job_state == JobState.CANCELED
        assert job.failure_reason == "canceled_by_user"

    app.dependency_overrides.clear()


def test_job_delete_rejects_active_job() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        job = seed_job(
            session, account_id=account.id, payload={"name": "Active"}, state=JobState.QUEUED
        )
        job_id = job.id
        session.commit()

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.delete(f"/api/jobs/{job_id}")

    assert response.status_code == 409
    assert response.json()["error_code"] == "JOB_ACTIVE_CANNOT_DELETE"
    with session_factory() as session:
        assert session.get(Job, job_id) is not None

    app.dependency_overrides.clear()


def test_job_delete_removes_terminal_job(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        job = seed_job(
            session, account_id=account.id, payload={"name": "Delete Me"}, state=JobState.CANCELED
        )
        job_id = job.id
        session.commit()

    removed: list[str] = []
    monkeypatch.setattr(
        "app.api.jobs.remove_job_from_queue",
        lambda next_job_id: removed.append(next_job_id) or True,
    )
    override_app_session(session_factory)
    client = TestClient(app)

    response = client.delete(f"/api/jobs/{job_id}")

    assert response.status_code == 204
    assert removed == [job_id]
    with session_factory() as session:
        assert session.get(Job, job_id) is None

    app.dependency_overrides.clear()


def test_unified_error_dto_shape_for_missing_account() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    override_app_session(session_factory)
    client = TestClient(app)

    response = client.get("/api/dashboard/profile/missing-account")

    assert response.status_code == 404
    payload = response.json()
    assert set(payload.keys()) == {
        "error_code",
        "error_class",
        "message",
        "details",
        "field_errors",
        "request_id",
    }
    assert payload["error_code"] == "ACCOUNT_NOT_FOUND"
    assert payload["error_class"] == "not_found"
    assert payload["field_errors"] == []
    assert payload["request_id"]

    app.dependency_overrides.clear()


def test_runtime_refresh_returns_frontend_friendly_shape(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        account.account_state = AccountState.AUTHORIZED_READY
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
    client = TestClient(app)

    response = client.post(f"/api/accounts/{account_id}/refresh-runtime")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {
        "account_id",
        "account_state",
        "runtime_health",
        "is_execution_usable",
        "last_error_code",
        "last_error_class",
        "refreshed_at",
    }
    assert payload["account_state"] == "execution_usable"
    assert payload["is_execution_usable"] is True

    with session_factory() as session:
        refreshed = session.get(type(account), account_id)
        assert refreshed.profile_state is not None
        assert refreshed.profile_state.first_name == "King"
        assert refreshed.profile_state.last_name == "Blackburn"
        assert refreshed.profile_state.username == "kingblackburn"
        assert refreshed.profile_state.bio == "Live from Telegram"

    app.dependency_overrides.clear()


def test_runtime_refresh_rolls_back_after_profile_sync_failure(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        account.account_state = AccountState.AUTHORIZED_READY
        account_id = account.id

    class BrokenProfileSyncAdapter:
        def fetch_profile_snapshot(self, account_id: str) -> dict:
            raise RuntimeError("sync failed")

    override_app_session(session_factory)
    monkeypatch.setattr(
        "app.modules.account_shared.runtime.build_profile_execution_adapter",
        lambda: FakeExecutionUsableAdapter(ok=True),
    )
    monkeypatch.setattr(
        "app.modules.account_shared.runtime.build_profile_sync_adapter",
        lambda: BrokenProfileSyncAdapter(),
    )
    client = TestClient(app)

    response = client.post(
        "/api/accounts/refresh-runtime",
        headers={"X-Account-Id": account_id},
    )

    assert response.status_code == 502
    assert response.json()["error_code"] == "PROFILE_SYNC_FAILED"

    app.dependency_overrides.clear()


def test_delete_story_post_removes_live_story(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        post = AccountStoryPost(
            account_id=account.id,
            story_poster_chat_id="777000",
            telegram_story_id="2",
            temporary_story_id=None,
            media_kind="video",
            asset_id=None,
            caption="Live story",
            privacy_preset="public",
            active_period_seconds=86400,
            protect_content=False,
            can_be_deleted=True,
            status="active",
            raw_tdlib_json={
                "id": 2,
                "poster_chat_id": 777000,
                "is_posted_to_chat_page": True,
                "can_toggle_is_posted_to_chat_page": True,
                "can_be_deleted": True,
            },
            created_at=datetime.now(UTC),
        )
        session.add(post)
        session.commit()
        account_id = account.id
        post_id = post.id

    adapter = FakeProfileSyncAdapter()
    override_app_session(session_factory)
    monkeypatch.setattr("app.api.story_posts.build_profile_sync_adapter", lambda: adapter)
    client = TestClient(app)

    response = client.delete(f"/api/story-posts/{post_id}", headers={"X-Account-Id": account_id})

    assert response.status_code == 204
    assert adapter.calls[-1] == f"delete:{account_id}:777000:2"
    with session_factory() as session:
        refreshed = session.get(AccountStoryPost, post_id)
        assert refreshed.status == "removed"

    app.dependency_overrides.clear()


def test_delete_story_post_hard_deletes_non_profile_story(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        post = AccountStoryPost(
            account_id=account.id,
            story_poster_chat_id="777000",
            telegram_story_id="2",
            temporary_story_id=None,
            media_kind="video",
            asset_id=None,
            caption="Live story",
            privacy_preset="public",
            active_period_seconds=86400,
            protect_content=False,
            can_be_deleted=True,
            status="active",
            raw_tdlib_json={
                "id": 2,
                "poster_chat_id": 777000,
                "is_posted_to_chat_page": False,
                "can_toggle_is_posted_to_chat_page": False,
                "can_be_deleted": True,
            },
            created_at=datetime.now(UTC),
        )
        session.add(post)
        session.commit()
        account_id = account.id
        post_id = post.id

    adapter = FakeProfileSyncAdapter()
    override_app_session(session_factory)
    monkeypatch.setattr("app.api.story_posts.build_profile_sync_adapter", lambda: adapter)
    client = TestClient(app)

    response = client.delete(f"/api/story-posts/{post_id}", headers={"X-Account-Id": account_id})

    assert response.status_code == 204
    assert adapter.calls[-1] == f"delete:{account_id}:777000:2"

    app.dependency_overrides.clear()


def test_delete_story_post_treats_missing_telegram_story_as_removed(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        post = AccountStoryPost(
            account_id=account.id,
            story_poster_chat_id="777000",
            telegram_story_id="2",
            temporary_story_id=None,
            media_kind="video",
            asset_id=None,
            caption="Live story",
            privacy_preset="public",
            active_period_seconds=86400,
            protect_content=False,
            can_be_deleted=True,
            status="active",
            raw_tdlib_json={"id": 2, "poster_chat_id": 777000, "can_be_deleted": True},
            created_at=datetime.now(UTC),
        )
        session.add(post)
        session.commit()
        account_id = account.id
        post_id = post.id

    class MissingStoryAdapter(FakeProfileSyncAdapter):
        def delete_story(
            self, account_id: str, story_poster_chat_id: str | None, story_id: str
        ) -> None:
            raise RuntimeError("Not Found")

    override_app_session(session_factory)
    monkeypatch.setattr(
        "app.api.story_posts.build_profile_sync_adapter", lambda: MissingStoryAdapter()
    )
    client = TestClient(app)

    response = client.delete(f"/api/story-posts/{post_id}", headers={"X-Account-Id": account_id})

    assert response.status_code == 204
    with session_factory() as session:
        refreshed = session.get(AccountStoryPost, post_id)
        assert refreshed.status == "removed"

    app.dependency_overrides.clear()


def test_delete_story_post_allows_profile_unpost_when_not_deletable(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        post = AccountStoryPost(
            account_id=account.id,
            story_poster_chat_id="777000",
            telegram_story_id="2",
            temporary_story_id=None,
            media_kind="video",
            asset_id=None,
            caption="Live story",
            privacy_preset="public",
            active_period_seconds=86400,
            protect_content=False,
            can_be_deleted=False,
            status="active",
            raw_tdlib_json={
                "id": 2,
                "poster_chat_id": 777000,
                "is_posted_to_chat_page": True,
                "can_toggle_is_posted_to_chat_page": True,
                "can_be_deleted": False,
            },
            created_at=datetime.now(UTC),
        )
        session.add(post)
        session.commit()
        account_id = account.id
        post_id = post.id

    adapter = FakeProfileSyncAdapter()
    override_app_session(session_factory)
    monkeypatch.setattr("app.api.story_posts.build_profile_sync_adapter", lambda: adapter)
    client = TestClient(app)

    response = client.delete(f"/api/story-posts/{post_id}", headers={"X-Account-Id": account_id})

    assert response.status_code == 204
    assert adapter.calls[-1] == f"unpost:{account_id}:777000:2"

    app.dependency_overrides.clear()


def test_delete_story_post_rejects_non_deletable_story(monkeypatch) -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)

    with session_factory() as session:
        account = create_account(session, external_ref="+15550102000")
        post = AccountStoryPost(
            account_id=account.id,
            story_poster_chat_id="777000",
            telegram_story_id="2",
            temporary_story_id=None,
            media_kind="video",
            asset_id=None,
            caption="Live story",
            privacy_preset="public",
            active_period_seconds=86400,
            protect_content=False,
            can_be_deleted=False,
            status="active",
            created_at=datetime.now(UTC),
        )
        session.add(post)
        session.commit()
        account_id = account.id
        post_id = post.id

    override_app_session(session_factory)
    monkeypatch.setattr(
        "app.api.story_posts.build_profile_sync_adapter", lambda: FakeProfileSyncAdapter()
    )
    client = TestClient(app)

    response = client.delete(f"/api/story-posts/{post_id}", headers={"X-Account-Id": account_id})

    assert response.status_code == 400
    assert response.json()["error_code"] == "STORY_POST_CANNOT_DELETE"

    app.dependency_overrides.clear()
