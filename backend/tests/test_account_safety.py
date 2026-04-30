from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import Base
from app.main import app
from app.models import (
    AccountOperationCooldown,
    AccountProfileState,
    AccountState,
    AccountStoryPost,
    JobState,
    JobStepResult,
    StepStatus,
)
from app.services.accounts import create_account
from app.services.database import create_sqlite_test_session_factory
from conftest import override_app_session, seed_audio_asset, seed_job, seed_story_asset


def test_account_safety_ready_for_execution_usable_account(db_session) -> None:
    from app.services.account_safety import build_account_safety

    account = create_account(db_session, external_ref="+15550102000")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.runtime_health = "ready"
    account.runtime_state.session_present = True
    account.runtime_state.reauth_required = False
    account.profile_state = AccountProfileState(account_id=account.id, first_name="Stylist")
    db_session.commit()

    safety = build_account_safety(db_session, account.id)

    assert safety["health_status"] == "ready"
    assert safety["overall_risk_level"] == "low"
    assert safety["capabilities"]["profile_text"]["state"] == "available"
    assert safety["risk_by_operation"]["profile_update"]["level"] == "low"


def test_account_safety_blocked_by_reauth_required(db_session) -> None:
    from app.services.account_safety import build_account_safety

    account = create_account(db_session, external_ref="+15550102001")
    account.account_state = AccountState.REAUTH_REQUIRED
    account.runtime_state.runtime_health = "closed"
    account.runtime_state.reauth_required = True
    db_session.commit()

    safety = build_account_safety(db_session, account.id)

    assert safety["health_status"] == "blocked"
    assert safety["overall_risk_level"] == "blocked"
    assert safety["capabilities"]["profile_text"]["state"] == "blocked"
    assert safety["risk_by_operation"]["story_post"]["level"] == "blocked"
    assert "reauth_required" in [reason["code"] for reason in safety["reasons"]]


def test_account_safety_attention_for_recent_partial_job(db_session) -> None:
    from app.services.account_safety import build_account_safety

    account = create_account(db_session, external_ref="+15550102002")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.runtime_health = "ready"
    account.profile_state = AccountProfileState(account_id=account.id, first_name="Stylist")
    seed_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist"},
        state=JobState.PARTIALLY_COMPLETED,
        finished_at=datetime.now(UTC),
    )
    db_session.commit()

    safety = build_account_safety(db_session, account.id)

    assert safety["health_status"] == "attention"
    assert safety["risk_by_operation"]["profile_update"]["level"] == "medium"
    assert "recent_partial_job" in [reason["code"] for reason in safety["reasons"]]


def test_account_safety_story_live_disabled_and_music_unknown(db_session) -> None:
    from app.services.account_safety import build_account_safety

    account = create_account(db_session, external_ref="+15550102003")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.runtime_health = "ready"
    db_session.commit()

    safety = build_account_safety(db_session, account.id)

    assert safety["capabilities"]["story_post"]["state"] == "blocked"
    assert safety["capabilities"]["profile_music"]["state"] == "unknown"
    assert safety["risk_by_operation"]["story_post"]["level"] == "blocked"


def test_account_safety_high_risk_for_recent_flood_wait(db_session) -> None:
    from app.services.account_safety import build_account_safety

    account = create_account(db_session, external_ref="+15550102004")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.runtime_health = "ready"
    job = seed_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist"},
        state=JobState.FAILED,
        finished_at=datetime.now(UTC),
    )
    db_session.add(
        JobStepResult(
            job_id=job.id,
            step_key="set_name",
            step_type="set_name",
            status=StepStatus.FAILED,
            error_code="FLOOD_WAIT_60",
            error_class="tdlib_error",
            finished_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    safety = build_account_safety(db_session, account.id)

    assert safety["risk_by_operation"]["profile_update"]["level"] == "blocked"
    assert "recent_flood_wait" in [reason["code"] for reason in safety["reasons"]]


def test_account_safety_summary_and_detail_endpoints() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = create_account(session, external_ref="+15550102005")
        account.account_state = AccountState.EXECUTION_USABLE
        account.runtime_state.runtime_health = "ready"
        account.profile_state = AccountProfileState(account_id=account.id, first_name="Stylist")
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    client = TestClient(app)

    summary = client.get("/api/accounts/safety-summary")
    detail = client.get(f"/api/accounts/{account_id}/safety")

    app.dependency_overrides.clear()

    assert summary.status_code == 200
    assert summary.json()[0]["account_id"] == account_id
    assert summary.json()[0]["health_status"] == "ready"
    assert detail.status_code == 200
    assert detail.json()["account_id"] == account_id
    assert "profile_text" in detail.json()["capabilities"]


def test_account_validity_check_db_snapshot_persists_run_and_snapshot() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = create_account(session, external_ref="+15550102007")
        account.account_state = AccountState.EXECUTION_USABLE
        account.runtime_state.runtime_health = "ready"
        account.profile_state = AccountProfileState(account_id=account.id, first_name="Stylist")
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.post(f"/api/accounts/{account_id}/validity-check", json={"mode": "db_snapshot"})
    checks = client.get(f"/api/accounts/{account_id}/validity-checks")
    safety = client.get(f"/api/accounts/{account_id}/safety")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["mode"] == "db_snapshot"
    assert response.json()["status"] == "completed"
    assert response.json()["result"]["health_status"] == "ready"
    assert checks.status_code == 200
    assert checks.json()[0]["status"] == "completed"
    assert safety.json()["last_validity_check"]["status"] == "completed"


def test_account_validity_check_tdlib_mode_is_safe_unsupported_without_live_action() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = create_account(session, external_ref="+15550102008")
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.post(f"/api/accounts/{account_id}/validity-check", json={"mode": "tdlib_readonly"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] in {"completed", "unsupported"}
    if response.json()["status"] == "completed":
        assert response.json()["result"]["validity_status"] in {"runtime_broken", "reauth_required", "unknown"}
    else:
        assert response.json()["error_code"] == "TDLIB_READONLY_CHECK_NOT_ENABLED"


def test_account_validity_tdlib_readonly_adapter_returns_valid_and_does_not_write(db_session) -> None:
    from app.services.account_validity import run_account_validity_check

    class FakeReadonlyAdapter:
        def __init__(self) -> None:
            self.write_calls: list[str] = []

        def check_account(self, account_id: str) -> dict:
            return {
                "status": "valid",
                "telegram_user_id": "123456",
                "runtime_health": "ready",
                "profile": {"first_name": "Stylist", "username": "stylisttg"},
            }

        def set_name(self, *_args, **_kwargs) -> None:
            self.write_calls.append("set_name")

    account = create_account(db_session, external_ref="+15550102010")
    adapter = FakeReadonlyAdapter()

    result = run_account_validity_check(db_session, account.id, mode="tdlib_readonly", adapter=adapter)

    assert result["status"] == "completed"
    assert result["result"]["validity_status"] == "valid"
    assert adapter.write_calls == []
    assert account.account_state == AccountState.EXECUTION_USABLE
    assert account.runtime_state.runtime_health == "ready"
    assert account.profile_state.username == "stylisttg"


def test_account_safety_reports_recent_flood_wait_without_writing_on_read(db_session) -> None:
    from app.services.account_safety import build_account_safety

    account = create_account(db_session, external_ref="+15550102011")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.runtime_health = "ready"
    account.profile_state = AccountProfileState(account_id=account.id, first_name="Stylist")
    finished_at = datetime.now(UTC)
    job = seed_job(db_session, account_id=account.id, payload={"username": "name"}, state=JobState.FAILED, finished_at=finished_at)
    db_session.add(
        JobStepResult(
            job_id=job.id,
            step_key="set_username",
            step_type="set_username",
            status=StepStatus.FAILED,
            error_code="FLOOD_WAIT_60",
            error_class="tdlib_error",
            finished_at=finished_at,
        )
    )
    db_session.commit()

    safety = build_account_safety(db_session, account.id)

    cooldown = safety["cooldowns_by_operation"]["username"][0]
    assert cooldown["level"] == "blocked"
    assert cooldown["reason_code"] == "recent_flood_wait"
    assert cooldown["retry_after_at"] > datetime.now(UTC)
    assert safety["risk_by_operation"]["username"]["level"] == "blocked"
    persisted = db_session.execute(select(AccountOperationCooldown).where(AccountOperationCooldown.account_id == account.id)).scalars().all()
    assert persisted == []


def test_validity_check_persists_operation_cooldown_from_flood_wait(db_session) -> None:
    from app.services.account_validity import run_account_validity_check

    account = create_account(db_session, external_ref="+15550102021")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.runtime_health = "ready"
    account.profile_state = AccountProfileState(account_id=account.id, first_name="Stylist")
    finished_at = datetime.now(UTC)
    job = seed_job(db_session, account_id=account.id, payload={"username": "name"}, state=JobState.FAILED, finished_at=finished_at)
    db_session.add(
        JobStepResult(
            job_id=job.id,
            step_key="set_username",
            step_type="set_username",
            status=StepStatus.FAILED,
            error_code="FLOOD_WAIT_60",
            error_class="tdlib_error",
            finished_at=finished_at,
        )
    )
    db_session.commit()

    run_account_validity_check(db_session, account.id)

    persisted = db_session.execute(select(AccountOperationCooldown).where(AccountOperationCooldown.account_id == account.id)).scalars().all()
    assert len(persisted) == 1
    assert persisted[0].operation == "username"


def test_expired_operation_cooldown_no_longer_blocks_safety(db_session) -> None:
    from app.services.account_safety import build_account_safety

    account = create_account(db_session, external_ref="+15550102012")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.runtime_health = "ready"
    account.profile_state = AccountProfileState(account_id=account.id, first_name="Stylist")
    db_session.add(
        AccountOperationCooldown(
            account_id=account.id,
            operation="username",
            level="blocked",
            reason_code="recent_flood_wait",
            started_at=datetime.now(UTC) - timedelta(minutes=10),
            retry_after_at=datetime.now(UTC) - timedelta(minutes=1),
            source="job_step_result",
        )
    )
    db_session.commit()

    safety = build_account_safety(db_session, account.id)

    assert safety["cooldowns_by_operation"]["username"] == []
    assert safety["risk_by_operation"]["username"]["level"] != "blocked"


def test_account_update_preview_blocks_only_affected_cooldown_operation(db_session) -> None:
    from app.services.account_update_jobs import build_account_update_preview

    account = create_account(db_session, external_ref="+15550102013")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.runtime_health = "ready"
    account.profile_state = AccountProfileState(account_id=account.id, first_name="Stylist")
    db_session.add(
        AccountOperationCooldown(
            account_id=account.id,
            operation="username",
            level="blocked",
            reason_code="recent_flood_wait",
            started_at=datetime.now(UTC),
            retry_after_at=datetime.now(UTC) + timedelta(minutes=5),
            source="job_step_result",
        )
    )
    db_session.commit()

    bio_preview = build_account_update_preview(
        db_session,
        account_id=account.id,
        desired_state={"profile": {"bio": "safe"}},
    )
    username_preview = build_account_update_preview(
        db_session,
        account_id=account.id,
        desired_state={"profile": {"username": "blocked_name"}},
    )

    assert bio_preview["can_create_job"] is True
    assert "cooldown_active:username" not in bio_preview["safety_blockers"]
    assert username_preview["can_create_job"] is False
    assert "cooldown_active:username" in username_preview["safety_blockers"]


def test_safety_preview_respects_unknown_capability_policy(db_session) -> None:
    from app.config import Settings
    from app.services.account_safety import build_account_safety, safety_preview_fields_with_policy

    account = create_account(db_session, external_ref="+15550102014")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.runtime_health = "ready"
    db_session.commit()

    safety = build_account_safety(db_session, account.id, config=Settings(unknown_capability_policy="block_live_execution"))
    fields = safety_preview_fields_with_policy(
        safety,
        {"profile_audio": {"action": "add", "audio_asset_id": "asset-1"}},
        config=Settings(unknown_capability_policy="block_live_execution"),
    )

    assert "music_capability_not_checked" in fields["safety_blockers"]


def test_safety_preview_requires_fresh_validity_for_live_policy(db_session) -> None:
    from app.config import Settings
    from app.services.account_safety import build_account_safety, safety_preview_fields_with_policy

    account = create_account(db_session, external_ref="+15550102015")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.runtime_health = "ready"
    db_session.commit()

    safety = build_account_safety(db_session, account.id, config=Settings(fresh_validity_required="always_for_live"))
    fields = safety_preview_fields_with_policy(
        safety,
        {"profile": {"bio": "updated"}},
        config=Settings(fresh_validity_required="always_for_live"),
    )

    assert "fresh_validity_required" in fields["safety_blockers"]
    assert fields["operation_safety"][0]["operation"] == "profile_update"
    assert fields["operation_safety"][0]["can_override"] is True


def test_safety_override_with_reason_allows_overridable_preview_blocker(db_session) -> None:
    from app.config import Settings
    from app.services.account_safety import build_account_safety, safety_preview_fields_with_policy
    from app.services.account_safety_overrides import create_safety_override

    account = create_account(db_session, external_ref="+15550102022")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.runtime_health = "ready"
    db_session.commit()
    create_safety_override(
        db_session,
        account.id,
        operation="profile_music",
        reason="Оператор проверил файл и принимает предупреждение",
        requested_blockers=["music_capability_not_checked"],
    )

    safety = build_account_safety(db_session, account.id, config=Settings(unknown_capability_policy="block_live_execution"))
    fields = safety_preview_fields_with_policy(
        safety,
        {"profile_audio": {"action": "add", "audio_asset_id": "asset-1"}},
        config=Settings(unknown_capability_policy="block_live_execution"),
    )

    assert "music_capability_not_checked" not in fields["safety_blockers"]
    assert "override_applied:profile_music" in fields["safety_warnings"]
    assert fields["operation_safety"][0]["state"] == "warning"


def test_safety_override_rejects_non_overridable_blocker(db_session) -> None:
    from app.services.account_safety_overrides import create_safety_override

    account = create_account(db_session, external_ref="+15550102023")
    db_session.commit()

    try:
        create_safety_override(
            db_session,
            account.id,
            operation="profile_update",
            reason="try hard override",
            requested_blockers=["reauth_required"],
        )
    except ValueError as exc:
        assert "non-overridable blocker" in str(exc)
    else:
        raise AssertionError("override should reject non-overridable blockers")


def test_recent_failure_policy_creates_warning_cooldown_for_soft_failure(db_session) -> None:
    from app.config import Settings
    from app.services.account_safety import build_account_safety

    account = create_account(db_session, external_ref="+15550102020")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.runtime_health = "ready"
    account.profile_state = AccountProfileState(account_id=account.id, first_name="Stylist")
    finished_at = datetime.now(UTC)
    job = seed_job(db_session, account_id=account.id, payload={"username": "taken"}, state=JobState.FAILED, finished_at=finished_at)
    db_session.add(
        JobStepResult(
            job_id=job.id,
            step_key="set_username",
            step_type="set_username",
            status=StepStatus.FAILED,
            error_code="USERNAME_INVALID",
            error_class="tdlib_error",
            finished_at=finished_at,
        )
    )
    db_session.commit()

    safety = build_account_safety(
        db_session,
        account.id,
        config=Settings(recent_failure_policy="cooldown", username_cooldown_seconds=900),
    )

    cooldown = safety["cooldowns_by_operation"]["username"][0]
    assert cooldown["level"] == "warning"
    assert cooldown["reason_code"] == "recent_failure_cooldown"


def test_account_capabilities_deepen_story_delete_and_username_failure(db_session) -> None:
    from app.services.account_safety import build_account_safety

    account = create_account(db_session, external_ref="+15550102009")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.runtime_health = "ready"
    account.profile_state = AccountProfileState(account_id=account.id, first_name="Stylist")
    db_session.add(
        AccountStoryPost(
            account_id=account.id,
            media_kind="image",
            status="posted",
            can_be_deleted=False,
            posted_at=datetime.now(UTC),
        )
    )
    job = seed_job(
        db_session,
        account_id=account.id,
        payload={"username": "taken"},
        state=JobState.FAILED,
        finished_at=datetime.now(UTC),
    )
    db_session.add(
        JobStepResult(
            job_id=job.id,
            step_key="set_username",
            step_type="set_username",
            status=StepStatus.FAILED,
            error_code="USERNAME_INVALID",
            error_class="tdlib_error",
            finished_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    safety = build_account_safety(db_session, account.id)

    assert safety["capabilities"]["story_delete"]["state"] == "limited"
    assert "story_delete_not_confirmed" in safety["capabilities"]["story_delete"]["reason_codes"]
    assert safety["risk_by_operation"]["username"]["level"] == "medium"


def test_account_update_preview_includes_safety_fields_and_preserves_steps(db_session) -> None:
    from app.services.account_update_jobs import build_account_update_preview

    account = create_account(db_session, external_ref="+15550102006")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.runtime_health = "ready"
    audio = seed_audio_asset(db_session)
    story = seed_story_asset(db_session)
    db_session.commit()

    preview = build_account_update_preview(
        db_session,
        account_id=account.id,
        desired_state={
            "profile": {"name": "Stylist", "username": "stylisttg"},
            "profile_audio": {"action": "add", "audio_asset_id": audio.id},
            "stories": [{"action": "post_image", "asset_id": story.id}],
        },
    )

    assert "account_safety" in preview
    assert "risk_by_operation" in preview
    assert preview["safety_blockers"]
    assert "stories_mock_mode" in preview["safety_blockers"]
    assert "add_profile_audio" in [step["step_type"] for step in preview["steps"]]
    assert "post_story_image" in [step["step_type"] for step in preview["steps"]]


def test_account_batch_safety_preview_blocks_accounts_with_hard_safety_state(db_session) -> None:
    from app.services.account_batch_safety import build_account_batch_safety_preview

    ready = create_account(db_session, external_ref="+15550102016")
    ready.account_state = AccountState.EXECUTION_USABLE
    ready.runtime_state.runtime_health = "ready"
    ready.profile_state = AccountProfileState(account_id=ready.id, first_name="Ready")

    blocked = create_account(db_session, external_ref="+15550102017")
    blocked.account_state = AccountState.REAUTH_REQUIRED
    blocked.runtime_state.runtime_health = "closed"
    blocked.runtime_state.reauth_required = True
    db_session.commit()

    preview = build_account_batch_safety_preview(
        db_session,
        account_ids=[ready.id, blocked.id],
        operation="profile_update",
    )

    assert preview["can_start"] is False
    assert preview["counts"]["ready"] == 1
    assert preview["counts"]["needs_login"] == 1
    assert blocked.id in preview["blocking_account_ids"]


def test_account_batch_safety_preview_marks_operation_cooldown_as_paused(db_session) -> None:
    from app.services.account_batch_safety import build_account_batch_safety_preview

    account = create_account(db_session, external_ref="+15550102018")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.runtime_health = "ready"
    account.profile_state = AccountProfileState(account_id=account.id, first_name="Paused")
    db_session.add(
        AccountOperationCooldown(
            account_id=account.id,
            operation="username",
            level="blocked",
            reason_code="recent_flood_wait",
            started_at=datetime.now(UTC),
            retry_after_at=datetime.now(UTC) + timedelta(minutes=5),
            source="job_step_result",
        )
    )
    db_session.commit()

    preview = build_account_batch_safety_preview(
        db_session,
        account_ids=[account.id],
        operation="username",
    )

    assert preview["can_start"] is False
    assert preview["counts"]["paused"] == 1
    assert preview["items"][0]["batch_status"] == "paused"


def test_account_batch_safety_preview_endpoint_returns_counts() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = create_account(session, external_ref="+15550102019")
        account.account_state = AccountState.EXECUTION_USABLE
        account.runtime_state.runtime_health = "ready"
        account.profile_state = AccountProfileState(account_id=account.id, first_name="Ready")
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.post(
        "/api/accounts/safety-batch-preview",
        json={"account_ids": [account_id], "operation": "profile_update"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["can_start"] is True
    assert response.json()["counts"]["ready"] == 1


def test_account_safety_override_endpoint_records_audit_entry() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        account = create_account(session, external_ref="+15550102024")
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    client = TestClient(app)

    response = client.post(
        f"/api/accounts/{account_id}/safety-overrides",
        json={
            "operation": "profile_music",
            "reason": "Оператор проверил предупреждение",
            "requested_blockers": ["music_capability_not_checked"],
        },
    )
    rejected = client.post(
        f"/api/accounts/{account_id}/safety-overrides",
        json={
            "operation": "profile_update",
            "reason": "Нельзя обходить вход",
            "requested_blockers": ["reauth_required"],
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["requested_blockers"] == ["music_capability_not_checked"]
    assert rejected.status_code == 400
