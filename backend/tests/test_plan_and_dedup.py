from datetime import timedelta

from pydantic_settings import SettingsConfigDict

from app.config import Settings
from app.models import AccountState, JobState, utc_now
from app.services.accounts import create_account
from app.services.jobs import create_profile_job, find_active_duplicate_job
from app.services.plan import build_profile_plan, compute_execution_intent_hash


class LocalSettings(Settings):
    model_config = SettingsConfigDict(env_file=None)


def test_execution_intent_hash_is_stable_for_same_payload() -> None:
    payload_a = {
        "username": "stylist",
        "name": "Stylist TG",
        "bio": "Profile editor",
        "photo_asset_id": "asset-1",
    }
    payload_b = {
        "photo_asset_id": "asset-1",
        "bio": "Profile editor",
        "name": "Stylist TG",
        "username": "stylist",
    }

    assert compute_execution_intent_hash("account-1", payload_a) == compute_execution_intent_hash(
        "account-1", payload_b
    )


def test_profile_plan_snapshot_contains_ordered_v0_steps() -> None:
    plan = build_profile_plan(
        {
            "name": "Stylist TG",
            "bio": "Profile editor",
            "username": "stylist",
            "photo_asset_id": "asset-1",
        }
    )

    assert plan["plan_version"] == 1
    assert plan["job_payload_version"] == 1
    assert [step["step_type"] for step in plan["steps"]] == [
        "set_name",
        "set_bio",
        "set_username",
        "set_profile_photo",
    ]
    assert all(step["required"] for step in plan["steps"])


def test_duplicate_active_profile_job_is_dedup_blocked(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    payload = {
        "name": "Stylist TG",
        "bio": "Profile editor",
        "username": "stylist",
        "photo_asset_id": None,
    }

    first = create_profile_job(db_session, account_id=account.id, payload=payload)
    duplicate = create_profile_job(db_session, account_id=account.id, payload=payload)

    assert first.job_state == JobState.QUEUED
    assert duplicate.job_state == JobState.DEDUP_BLOCKED
    assert duplicate.dedup_blocked_by_job_id == first.id
    assert find_active_duplicate_job(db_session, account.id, first.execution_intent_hash).id == first.id


def test_repeated_duplicate_profile_jobs_do_not_hit_unique_constraint(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    payload = {
        "name": "Stylist TG",
        "bio": "Profile editor",
        "username": "stylist",
        "photo_asset_id": None,
    }

    first = create_profile_job(db_session, account_id=account.id, payload=payload)
    duplicate_a = create_profile_job(db_session, account_id=account.id, payload=payload)
    duplicate_b = create_profile_job(db_session, account_id=account.id, payload=payload)

    assert first.job_state == JobState.QUEUED
    assert duplicate_a.job_state == JobState.DEDUP_BLOCKED
    assert duplicate_b.job_state == JobState.DEDUP_BLOCKED
    assert duplicate_a.dedup_blocked_by_job_id == first.id
    assert duplicate_b.dedup_blocked_by_job_id == first.id


def test_same_profile_intent_can_be_created_after_previous_job_is_terminal(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    payload = {
        "name": "Stylist TG",
        "bio": "Profile editor",
        "username": "stylist",
        "photo_asset_id": None,
    }
    first = create_profile_job(
        db_session,
        account_id=account.id,
        payload=payload,
        config=LocalSettings(profile_job_cooldown_seconds=0),
    )
    first.job_state = JobState.COMPLETED
    first.finished_at = utc_now()
    db_session.commit()

    second = create_profile_job(
        db_session,
        account_id=account.id,
        payload=payload,
        config=LocalSettings(profile_job_cooldown_seconds=0),
    )

    assert second.job_state == JobState.QUEUED


def test_profile_job_blocks_when_account_requires_manual_intervention(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.MANUAL_INTERVENTION_NEEDED
    account.runtime_state.recovery_marker = "tdlib_hard_stop:FROZEN_METHOD_INVALID"
    db_session.commit()

    try:
        create_profile_job(
            db_session,
            account_id=account.id,
            payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "account requires manual intervention"


def test_profile_job_blocks_during_success_cooldown(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    existing = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "First", "bio": None, "username": None, "photo_asset_id": None},
        config=LocalSettings(profile_job_cooldown_seconds=0),
    )
    existing.job_state = JobState.COMPLETED
    existing.finished_at = utc_now() - timedelta(seconds=30)
    db_session.commit()

    try:
        create_profile_job(
            db_session,
            account_id=account.id,
            payload={"name": "Second", "bio": None, "username": None, "photo_asset_id": None},
            config=LocalSettings(profile_job_cooldown_seconds=300),
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "profile job cooldown active"
