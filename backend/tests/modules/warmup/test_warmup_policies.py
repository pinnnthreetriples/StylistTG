from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models import WarmupExecutionMode, WarmupStatus
from app.modules.warmup.errors import (
    WarmupPauseRejectedError,
    WarmupResumeRejectedError,
    WarmupSessionRejectedError,
)
from app.modules.warmup.policies import (
    can_create_warmup_session,
    can_pause_warmup_session,
    can_resume_warmup_session,
    is_live_warmup_mode,
    is_warmup_active_status,
    validate_session_status_transition,
    warmup_operation_policy,
)


def test_live_warmup_mode_only_treats_dry_run_as_non_live() -> None:
    assert not is_live_warmup_mode(WarmupExecutionMode.DRY_RUN.value)
    assert is_live_warmup_mode(WarmupExecutionMode.NETWORK.value)
    assert is_live_warmup_mode("unexpected")


def test_warmup_active_status_matches_active_status_enum_members() -> None:
    assert is_warmup_active_status(WarmupStatus.SCHEDULED.value)
    assert is_warmup_active_status(WarmupStatus.ACTIVE.value)
    assert not is_warmup_active_status(WarmupStatus.COMPLETED.value)
    assert not is_warmup_active_status("scheduled ")


def test_create_warmup_session_joins_all_blocking_reasons() -> None:
    can_create_warmup_session([])

    with pytest.raises(WarmupSessionRejectedError, match="first; second"):
        can_create_warmup_session(["first", "second"])


def test_pause_and_resume_status_boundaries() -> None:
    can_pause_warmup_session(WarmupStatus.SCHEDULED)
    can_pause_warmup_session(WarmupStatus.ACTIVE)

    with pytest.raises(WarmupPauseRejectedError):
        can_pause_warmup_session(WarmupStatus.COMPLETED)

    now = datetime(2026, 5, 18, tzinfo=UTC)
    can_resume_warmup_session(WarmupStatus.PAUSED_MANUAL, next_attempt_at=now, now=now)
    can_resume_warmup_session(
        WarmupStatus.PAUSED_RISK, next_attempt_at=now - timedelta(seconds=1), now=now
    )

    with pytest.raises(WarmupResumeRejectedError):
        can_resume_warmup_session(WarmupStatus.ACTIVE, next_attempt_at=None, now=now)
    with pytest.raises(WarmupResumeRejectedError, match="retry_not_ready"):
        can_resume_warmup_session(
            WarmupStatus.PAUSED_MANUAL,
            next_attempt_at=now + timedelta(seconds=1),
            now=now,
        )


def test_validate_session_status_transition_rejects_unknown_action_and_missing_clock() -> None:
    now = datetime(2026, 5, 18, tzinfo=UTC)
    validate_session_status_transition(action="pause", current_status=WarmupStatus.ACTIVE)
    validate_session_status_transition(
        action="resume",
        current_status=WarmupStatus.PAUSED_MANUAL,
        next_attempt_at=now,
        now=now,
    )

    with pytest.raises(WarmupResumeRejectedError):
        validate_session_status_transition(
            action="resume",
            current_status=WarmupStatus.PAUSED_MANUAL,
        )
    with pytest.raises(WarmupSessionRejectedError, match="unsupported warmup status transition"):
        validate_session_status_transition(action="delete", current_status=WarmupStatus.ACTIVE)


def test_warmup_operation_policy_locks_only_sensitive_operations() -> None:
    session = SimpleNamespace(id="session-1", status=WarmupStatus.ACTIVE.value, current_day=3)

    locked = warmup_operation_policy(warmup_session=session, operation="profile_update")
    allowed = warmup_operation_policy(warmup_session=session, operation="read_profile")
    without_session = warmup_operation_policy(warmup_session=None, operation="profile_update")

    assert locked == {
        "session_id": "session-1",
        "status": WarmupStatus.ACTIVE.value,
        "current_day": 3,
        "is_locked": True,
        "reason": "Аккаунт находится в подготовке",
    }
    assert allowed["is_locked"] is False
    assert allowed["reason"] is None
    assert without_session == {
        "session_id": None,
        "status": None,
        "current_day": None,
        "is_locked": False,
        "reason": None,
    }
