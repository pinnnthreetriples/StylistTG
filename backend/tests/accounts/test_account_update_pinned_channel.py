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


def test_cross_workspace_channel_ref_produces_blocking_error(db_session) -> None:
    """Cross-workspace ref → blocking_errors includes 'cross_workspace_channel_ref'."""
    from app.modules.account_editing.policies import AccountEditingPolicy
    from app.config import Settings
    from app.models import Account, AccountRuntimeState, new_id

    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    db_session.flush()

    # Directly insert an account record with a different workspace_id to simulate
    # cross-workspace ownership without needing a full workspace + plan + user setup
    foreign_account_id = new_id()
    foreign_ws_id = new_id()
    foreign_account = Account(
        id=foreign_account_id,
        workspace_id=foreign_ws_id,
        external_ref="foreign",
        account_state=AccountState.REGISTERED,
    )
    foreign_account.runtime_state = AccountRuntimeState(
        session_present=False, runtime_health="unknown", reauth_required=False
    )
    db_session.add(foreign_account)
    db_session.flush()

    desired = _desired_with_pinned_channel(foreign_account_id)
    policy = AccountEditingPolicy(db_session)
    config = Settings()

    blocking_errors, _warnings, _safety = policy.preview_safety(
        account=account,
        account_id=account.id,
        desired_state=desired,
        config=config,
    )

    assert "cross_workspace_channel_ref" in blocking_errors


def test_executor_calls_tdlib_set_personal_chat_with_correct_chat_id(db_session) -> None:
    """Executor calls TDLib setPersonalChat with correct chat_id."""
    # Test the TDLib query builder directly
    step = {"step_type": "set_pinned_channel", "payload": {"pinned_channel_ref": "-1001234567890"}}
    query = map_step_to_tdlib_query(step)
    assert query == {"@type": "setPersonalChat", "chat_id": -1001234567890}

    # Also test unpin (empty ref → chat_id 0)
    step_unpin = {"step_type": "set_pinned_channel", "payload": {"pinned_channel_ref": ""}}
    query_unpin = map_step_to_tdlib_query(step_unpin)
    assert query_unpin == {"@type": "setPersonalChat", "chat_id": 0}

    # Test full execution via mock adapter
    account = create_account(db_session, external_ref="primary")
    desired = profile_payload_to_account_update_desired_state(
        {
            "name": "Stylist TG",
            "pinned_channel_ref": "-1001234567890",
        }
    )
    job = create_account_update_job(db_session, account_id=account.id, desired_state=desired)

    exit_code = execute_account_update_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code == 0
    assert job.job_state == JobState.COMPLETED

    pinned_steps = [
        s for s in job.step_results if s.step_type == "set_pinned_channel"
    ]
    assert len(pinned_steps) == 1
    assert pinned_steps[0].status == StepStatus.SUCCEEDED
