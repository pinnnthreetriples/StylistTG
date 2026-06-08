from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import (
    AccountProfileState,
    DEFAULT_LOCAL_USER_ID,
    DEFAULT_LOCAL_WORKSPACE_ID,
    WarmupEvent,
    WarmupPreProductionSession,
)
from app.modules.account_lifecycle.interfaces import AccountLifecycleState
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated, require_mutation_permission
from app.modules.warmup import pre_production
from app.modules.warmup.dispatch_results import _complete_dispatch_session
from app.modules.warmup.module import module
from app.modules.warmup.pre_production import (
    PreProductionRejectedError,
    complete_due_pre_production_sessions,
    complete_pre_production_session,
    start_pre_production,
)
from tests.helpers.warmup import seed_warmup_account, seed_warmup_session, seed_warmup_strategy

NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


def test_start_pre_production_requires_enabled_flag(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    account.lifecycle_state = AccountLifecycleState.PRE_PRODUCTION.value
    db_session.commit()

    with pytest.raises(PreProductionRejectedError, match="disabled"):
        start_pre_production(
            db_session,
            account_id=account.id,
            workspace_id=account.workspace_id,
            config=SimpleNamespace(
                warmup_pre_production_enabled=False,
                warmup_pre_production_duration_hours=2,
            ),
            now=NOW,
        )


def test_start_pre_production_creates_empty_profile_dry_run_plan(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    account.lifecycle_state = AccountLifecycleState.WARMING.value
    db_session.commit()

    row = start_pre_production(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        target_channels=[{"channel_ref": "@bootstrap_a"}, "@bootstrap_b"],
        config=_enabled_config(),
        now=NOW,
    )

    assert account.lifecycle_state == AccountLifecycleState.PRE_PRODUCTION.value
    assert row.status == "running"
    assert row.duration_hours == 2
    assert row.ends_at == NOW + timedelta(hours=2)
    assert row.task_plan_json["mode"] == "dry_run"
    assert row.task_plan_json["neuro_comment"]["source_module"] == "neuro_commenting"
    assert 3 <= row.task_plan_json["neuro_comment"]["comment_count"] <= 5
    assert row.task_plan_json["mass_react"]["action"] == "react_to_post"
    assert 5 <= row.task_plan_json["mass_react"]["reaction_count"] <= 10
    assert row.task_plan_json["mass_react"]["target_channels"] == [
        "@bootstrap_a",
        "@bootstrap_b",
    ]


def test_start_pre_production_rejects_non_empty_profile(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    account.lifecycle_state = AccountLifecycleState.PRE_PRODUCTION.value
    account.profile_state = AccountProfileState(account_id=account.id, bio="not empty")
    db_session.commit()

    with pytest.raises(PreProductionRejectedError, match="bio"):
        start_pre_production(
            db_session,
            account_id=account.id,
            workspace_id=account.workspace_id,
            config=_enabled_config(),
            now=NOW,
        )


def test_pre_production_flood_wait_returns_account_to_cold_soak(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    account.lifecycle_state = AccountLifecycleState.PRE_PRODUCTION.value
    db_session.commit()
    row = start_pre_production(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        config=_enabled_config(),
        now=NOW,
    )

    completed = complete_pre_production_session(
        db_session,
        pre_production_session_id=row.id,
        workspace_id=account.workspace_id,
        success=False,
        failure_code="FLOOD_WAIT_60",
        now=NOW + timedelta(minutes=30),
    )

    assert completed.status == "failed"
    assert completed.failure_code == "FLOOD_WAIT_60"
    assert account.lifecycle_state == AccountLifecycleState.COLD_SOAK.value


def test_due_pre_production_expiry_marks_clean_session_active(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    account.lifecycle_state = AccountLifecycleState.PRE_PRODUCTION.value
    db_session.commit()
    row = start_pre_production(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        config=_enabled_config(warmup_pre_production_duration_hours=1),
        now=NOW,
    )

    processed = complete_due_pre_production_sessions(
        db_session,
        workspace_id=account.workspace_id,
        now=NOW + timedelta(hours=1, seconds=1),
    )

    assert processed == 1
    assert row.status == "completed"
    assert account.lifecycle_state == AccountLifecycleState.ACTIVE.value


def test_warmup_completion_starts_pre_production_when_strategy_flag_enabled(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pre_production.settings, "warmup_pre_production_enabled", True)
    strategy = seed_warmup_strategy(db_session, target_channels=[{"channel_ref": "@bootstrap"}])
    strategy.tier_limits_json = {"enable_pre_production": True}
    account = seed_warmup_account(db_session)
    warmup_session = seed_warmup_session(db_session, account=account, strategy=strategy, now=NOW)
    warmup_session.strategy_snapshot_json = {
        "tier_limits_json": {"enable_pre_production": True},
        "target_channels_json": [{"channel_ref": "@snapshot_bootstrap"}],
    }
    db_session.commit()

    _complete_dispatch_session(db_session, warmup_session, now=NOW + timedelta(days=3))

    row = db_session.scalar(
        select(WarmupPreProductionSession).where(
            WarmupPreProductionSession.account_id == account.id
        )
    )
    assert row is not None
    assert row.source_warmup_session_id == warmup_session.id
    assert row.task_plan_json["neuro_comment"]["target_channels"] == ["@snapshot_bootstrap"]
    assert "pre_production_started" in _warmup_event_types(db_session, warmup_session.id)


def test_pre_production_api_start_and_status(
    db_session: Session,
    app_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pre_production.settings, "warmup_pre_production_enabled", True)
    account = seed_warmup_account(db_session)
    account.lifecycle_state = AccountLifecycleState.WARMING.value
    db_session.commit()
    auth = AuthContext(
        user_id=DEFAULT_LOCAL_USER_ID,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="operator",
        auth_source="test",
    )
    app.dependency_overrides[require_authenticated] = lambda: auth
    app.dependency_overrides[require_mutation_permission] = lambda: auth

    response = app_client.post(
        f"/api/accounts/{account.id}/pre-production/start",
        json={"duration_hours": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["account_id"] == account.id
    assert payload["status"] == "running"
    assert payload["task_plan"]["empty_profile_required"] is True

    status_response = app_client.get(f"/api/accounts/{account.id}/pre-production/status")
    assert status_response.status_code == 200
    assert status_response.json()["session_id"] == payload["session_id"]


def test_pre_production_api_start_returns_conflict_when_disabled(
    db_session: Session,
    app_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pre_production.settings, "warmup_pre_production_enabled", False)
    account = seed_warmup_account(db_session)
    account.lifecycle_state = AccountLifecycleState.WARMING.value
    db_session.commit()
    auth = AuthContext(
        user_id=DEFAULT_LOCAL_USER_ID,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="operator",
        auth_source="test",
    )
    app.dependency_overrides[require_authenticated] = lambda: auth
    app.dependency_overrides[require_mutation_permission] = lambda: auth

    response = app_client.post(
        f"/api/accounts/{account.id}/pre-production/start",
        json={"duration_hours": 1},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "PRE_PRODUCTION_REJECTED"


def test_pre_production_sweep_workflow_is_registered() -> None:
    workflow_types = {workflow.workflow_type for workflow in module.workflows}

    assert "warmup_pre_production_sweep" in workflow_types


def _enabled_config(**overrides):
    defaults = {
        "warmup_pre_production_enabled": True,
        "warmup_pre_production_duration_hours": 2,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _warmup_event_types(session: Session, session_id: str) -> list[str]:
    return list(
        session.execute(
            select(WarmupEvent.event_type).where(WarmupEvent.session_id == session_id)
        ).scalars()
    )
