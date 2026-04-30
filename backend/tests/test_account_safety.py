from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.db import Base
from app.main import app
from app.models import AccountProfileState, AccountState, AccountStoryPost, JobState, JobStepResult, StepStatus
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

    assert safety["risk_by_operation"]["profile_update"]["level"] == "high"
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
    assert response.json()["status"] == "unsupported"
    assert response.json()["error_code"] == "TDLIB_READONLY_CHECK_NOT_ENABLED"


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
