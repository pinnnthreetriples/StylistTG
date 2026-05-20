"""Tests for the pinned channel (set_pinned_channel / setPersonalChat) operation."""

from app.adapters.tdlib_profile_execution import map_step_to_tdlib_query
from app.models import AccountState, JobState, StepStatus
from app.services.account_update_jobs import create_account_update_job
from app.services.account_update_plan import (
    build_account_update_plan,
    normalize_account_update_desired_state,
    profile_payload_to_account_update_desired_state,
)
from app.services.accounts import create_account
from app.workers.account_update_jobs import execute_account_update_job


def _desired_with_pinned_channel(channel_ref: str | None) -> dict:
    return normalize_account_update_desired_state(
        {
            "profile": {
                "name": "Stylist TG",
                "pinned_channel_ref": channel_ref,
            },
        }
    )


def _preview_with_channel_ref(db_session, channel_ref: str | None) -> tuple[list[str], list[str]]:
    from app.modules.account_editing.policies import AccountEditingPolicy
    from app.config import Settings

    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    db_session.flush()

    desired = _desired_with_pinned_channel(channel_ref)
    policy = AccountEditingPolicy(db_session)
    config = Settings()
    blocking_errors, warnings, _safety = policy.preview_safety(
        account=account,
        account_id=account.id,
        desired_state=desired,
        config=config,
    )
    return blocking_errors, warnings


def test_pinned_channel_ref_plans_set_pinned_channel_step() -> None:
    """Valid channel_ref → preview ok, step planned."""
    desired = _desired_with_pinned_channel("-1001234567890")
    plan = build_account_update_plan(desired)

    step_types = [step["step_type"] for step in plan["steps"]]
    assert "set_pinned_channel" in step_types

    pinned_step = next(s for s in plan["steps"] if s["step_type"] == "set_pinned_channel")
    assert pinned_step["payload"]["pinned_channel_ref"] == "-1001234567890"
    assert pinned_step["capability_key"] == "profile_text"
    assert pinned_step["compensation_policy"] == "manual_only"


def test_empty_pinned_channel_ref_still_included_in_plan() -> None:
    """Empty/None channel_ref → step is still in plan (sets chat_id=0 to unpin)."""
    desired = _desired_with_pinned_channel(None)
    plan = build_account_update_plan(desired)

    step_types = [step["step_type"] for step in plan["steps"]]
    assert "set_pinned_channel" in step_types

    pinned_step = next(s for s in plan["steps"] if s["step_type"] == "set_pinned_channel")
    assert pinned_step["payload"]["pinned_channel_ref"] is None


def test_invalid_channel_ref_produces_blocking_error(db_session) -> None:
    """Invalid channel_ref (not @username, not -100xxx) → blocking_errors includes 'invalid_channel_ref'."""
    blocking_errors, _ = _preview_with_channel_ref(db_session, "invalid")
    assert "invalid_channel_ref" in blocking_errors


def test_username_channel_ref_is_accepted(db_session) -> None:
    """@username channel_ref → no invalid_channel_ref in blocking_errors."""
    blocking_errors, _ = _preview_with_channel_ref(db_session, "@valid_channel")
    assert "invalid_channel_ref" not in blocking_errors


def test_numeric_channel_ref_is_accepted(db_session) -> None:
    """Numeric -100xxx channel_ref → no invalid_channel_ref in blocking_errors."""
    blocking_errors, _ = _preview_with_channel_ref(db_session, "-1001234567890")
    assert "invalid_channel_ref" not in blocking_errors


def test_executor_calls_tdlib_set_personal_chat_with_correct_chat_id(db_session) -> None:
    """Executor calls TDLib setPersonalChat with correct chat_id for numeric ref."""
    step = {"step_type": "set_pinned_channel", "payload": {"pinned_channel_ref": "-1001234567890"}}
    query = map_step_to_tdlib_query(step)
    assert query == {"@type": "setPersonalChat", "chat_id": -1001234567890}

    step_unpin = {"step_type": "set_pinned_channel", "payload": {"pinned_channel_ref": ""}}
    query_unpin = map_step_to_tdlib_query(step_unpin)
    assert query_unpin == {"@type": "setPersonalChat", "chat_id": 0}

    account = create_account(db_session, external_ref="primary")
    desired = profile_payload_to_account_update_desired_state(
        {"name": "Stylist TG", "pinned_channel_ref": "-1001234567890"}
    )
    job = create_account_update_job(db_session, account_id=account.id, desired_state=desired)
    exit_code = execute_account_update_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code == 0
    assert job.job_state == JobState.COMPLETED

    pinned_steps = [s for s in job.step_results if s.step_type == "set_pinned_channel"]
    assert len(pinned_steps) == 1
    assert pinned_steps[0].status == StepStatus.SUCCEEDED


def test_username_resolved_via_search_public_chat(db_session) -> None:
    """@username ref → mock adapter resolves to a numeric chat_id and succeeds."""
    step = {"step_type": "set_pinned_channel", "payload": {"pinned_channel_ref": "@test_channel"}}
    query = map_step_to_tdlib_query(step)
    assert query == {"@type": "searchPublicChat", "username": "test_channel"}

    account = create_account(db_session, external_ref="primary")
    desired = profile_payload_to_account_update_desired_state(
        {"name": "Stylist TG", "pinned_channel_ref": "@test_channel"}
    )
    job = create_account_update_job(db_session, account_id=account.id, desired_state=desired)
    exit_code = execute_account_update_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code == 0
    assert job.job_state == JobState.COMPLETED

    pinned_steps = [s for s in job.step_results if s.step_type == "set_pinned_channel"]
    assert len(pinned_steps) == 1
    assert pinned_steps[0].status == StepStatus.SUCCEEDED
    result_payload = pinned_steps[0].result_payload_json or {}
    applied = result_payload.get("applied", {})
    assert "_resolved_chat_id" in applied


def test_username_not_found_marks_step_failed(db_session) -> None:
    """searchPublicChat returns error → step.status = FAILED, error_code = pinned_channel_not_found."""
    account = create_account(db_session, external_ref="primary")
    desired = profile_payload_to_account_update_desired_state(
        {"name": "Stylist TG", "pinned_channel_ref": "@nonexistent_ch"}
    )
    job = create_account_update_job(
        db_session,
        account_id=account.id,
        desired_state=desired,
    )
    job.payload_json = {**(job.payload_json or {}), "mock_fail_pinned_channel": "@nonexistent_ch"}
    db_session.flush()

    exit_code = execute_account_update_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code != 0
    assert job.job_state in {JobState.FAILED, JobState.PARTIALLY_COMPLETED}

    pinned_steps = [s for s in job.step_results if s.step_type == "set_pinned_channel"]
    assert len(pinned_steps) == 1
    assert pinned_steps[0].status == StepStatus.FAILED
    assert pinned_steps[0].error_code == "pinned_channel_not_found"
