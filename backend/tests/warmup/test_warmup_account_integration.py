from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    WarmupStatus,
)
from app.services.accounts import list_accounts
from app.services.warmup import active_warmup_for_account, warmup_operation_policy
from tests.helpers.warmup import seed_warmup_account, seed_warmup_session_raw, seed_warmup_strategy


def test_account_exposes_derived_active_warmup_state(db_session) -> None:
    account = seed_warmup_account(db_session, with_proxy=False)
    strategy = seed_warmup_strategy(db_session, is_preset=True)
    warmup_session = seed_warmup_session_raw(
        db_session, account.id, strategy.id, WarmupStatus.ACTIVE
    )

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
    account = seed_warmup_account(db_session, with_proxy=False)
    strategy = seed_warmup_strategy(db_session, is_preset=True)
    seed_warmup_session_raw(db_session, account.id, strategy.id, WarmupStatus.ACTIVE)

    policy = warmup_operation_policy(
        db_session,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        operation="profile_update",
    )

    assert policy["is_locked"] is True
    assert policy["status"] == WarmupStatus.ACTIVE
    assert "Аккаунт находится в подготовке" in policy["reason"]


def test_account_update_job_is_blocked_during_active_warmup(app_client, db_session) -> None:
    account = seed_warmup_account(db_session, with_proxy=False)
    strategy = seed_warmup_strategy(db_session, is_preset=True)
    seed_warmup_session_raw(db_session, account.id, strategy.id, WarmupStatus.ACTIVE)

    response = app_client.post(
        "/api/account-update/jobs",
        json={"account_id": account.id, "profile": {"name": "Blocked"}},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "ACCOUNT_WARMUP_LOCKED"


def test_proxy_change_is_blocked_during_active_warmup(app_client, db_session) -> None:
    account = seed_warmup_account(db_session, with_proxy=False)
    strategy = seed_warmup_strategy(db_session, is_preset=True)
    seed_warmup_session_raw(db_session, account.id, strategy.id, WarmupStatus.ACTIVE)

    response = app_client.put(
        f"/api/accounts/{account.id}/proxy",
        json={"proxy_type": "socks5", "host": "127.0.0.1", "port": 1080},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "ACCOUNT_WARMUP_LOCKED"
