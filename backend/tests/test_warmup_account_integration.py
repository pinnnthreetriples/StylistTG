from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app
from app.models import (
    AccountRuntimeState,
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    WarmupSession,
    WarmupStatus,
    WarmupStrategy,
    new_id,
)
from app.services.accounts import create_account, list_accounts
from app.services.warmup import active_warmup_for_account, warmup_operation_policy


def test_account_exposes_derived_active_warmup_state(db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    warmup_session = _seed_warmup_session(db_session, account.id, strategy.id, WarmupStatus.ACTIVE)

    account_from_list = list_accounts(db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID)[0]
    warmup = active_warmup_for_account(
        db_session,
        account_id=account_from_list.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert warmup is not None
    assert warmup.id == warmup_session.id
    assert warmup.status == WarmupStatus.ACTIVE


def test_warmup_operation_policy_locks_conflicting_actions(db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    _seed_warmup_session(db_session, account.id, strategy.id, WarmupStatus.ACTIVE)

    policy = warmup_operation_policy(
        db_session,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        operation="profile_update",
    )

    assert policy["is_locked"] is True
    assert policy["status"] == WarmupStatus.ACTIVE
    assert "Аккаунт находится в подготовке" in policy["reason"]


def test_account_update_job_is_blocked_during_active_warmup(db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    _seed_warmup_session(db_session, account.id, strategy.id, WarmupStatus.ACTIVE)

    app.dependency_overrides[get_session] = _override_session(db_session)
    client = TestClient(app)
    response = client.post(
        "/api/account-update/jobs",
        json={"account_id": account.id, "profile": {"name": "Blocked"}},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error_code"] == "ACCOUNT_WARMUP_LOCKED"


def test_proxy_change_is_blocked_during_active_warmup(db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    _seed_warmup_session(db_session, account.id, strategy.id, WarmupStatus.ACTIVE)

    app.dependency_overrides[get_session] = _override_session(db_session)
    client = TestClient(app)
    response = client.put(
        f"/api/accounts/{account.id}/proxy",
        json={"proxy_type": "socks5", "host": "127.0.0.1", "port": 1080},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error_code"] == "ACCOUNT_WARMUP_LOCKED"


def _seed_ready_account(db_session):
    account = create_account(
        db_session,
        external_ref=f"+7999{new_id()[:8]}",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state = AccountRuntimeState(
        account_id=account.id,
        session_present=True,
        runtime_health="ready",
        reauth_required=False,
    )
    db_session.commit()
    return account


def _seed_strategy(db_session) -> WarmupStrategy:
    strategy = WarmupStrategy(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        name=f"Стратегия {new_id()[:8]}",
        description="Тестовая стратегия",
        tier_limits_json={},
        target_channels_json=[],
        is_preset=True,
    )
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _seed_warmup_session(db_session, account_id: str, strategy_id: str, status: str) -> WarmupSession:
    warmup_session = WarmupSession(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_id=account_id,
        strategy_id=strategy_id,
        status=status,
        current_day=4,
        cadence_hours=24,
    )
    db_session.add(warmup_session)
    db_session.commit()
    return warmup_session


def _override_session(session):
    def _override():
        yield session

    return _override
