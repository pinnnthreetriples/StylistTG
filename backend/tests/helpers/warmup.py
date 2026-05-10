"""Shared warmup seed factories for test modules.

Consolidates duplicated helpers from test_warmup_passive.py,
test_warmup_network_advanced.py, and test_warmup_account_integration.py.
"""
from __future__ import annotations

from datetime import UTC, datetime

from app.models import (
    AccountProxy,
    AccountRuntimeState,
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    ProxyCategory,
    WarmupExecutionMode,
    WarmupPresetKind,
    WarmupSession,
    WarmupStrategy,
    new_id,
)
from app.services.accounts import create_account
from app.services.warmup import create_warmup_session


def seed_warmup_account(
    db_session,
    *,
    with_proxy: bool = True,
    telegram_user_id: str | None = None,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
):
    """Create an EXECUTION_USABLE account with runtime state and optional proxy."""
    account = create_account(
        db_session,
        external_ref=f"+7999{new_id()[:8]}",
        workspace_id=workspace_id,
    )
    account.account_state = AccountState.EXECUTION_USABLE
    if telegram_user_id is not None:
        account.telegram_user_id = telegram_user_id
    account.runtime_state = AccountRuntimeState(
        account_id=account.id,
        session_present=True,
        runtime_health="ready",
        reauth_required=False,
    )
    if with_proxy:
        account.proxy = AccountProxy(
            account_id=account.id,
            proxy_type="socks5",
            proxy_category=ProxyCategory.RESIDENTIAL.value,
            host="127.0.0.1",
            port=1080,
            username="user",
            password_encrypted=None,
            status="ok",
        )
    db_session.commit()
    return account


def seed_warmup_strategy(
    db_session,
    *,
    execution_mode: str = WarmupExecutionMode.PASSIVE.value,
    target_channels: list | None = None,
    daily_action_limits: dict | None = None,
    duration_days: int = 3,
    is_preset: bool = False,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
) -> WarmupStrategy:
    """Create a WarmupStrategy with sensible defaults."""
    strategy = WarmupStrategy(
        id=new_id(),
        workspace_id=workspace_id,
        name=f"{execution_mode} {new_id()[:6]}",
        description=f"{execution_mode} test strategy",
        tier_limits_json={"cadence_hours": 24},
        target_channels_json=target_channels or [],
        is_preset=is_preset,
        execution_mode=execution_mode,
        preset_kind=WarmupPresetKind.STANDARD.value,
        duration_days=duration_days,
        daily_action_limits_json=daily_action_limits or {},
    )
    db_session.add(strategy)
    db_session.commit()
    return strategy


def seed_warmup_session(
    db_session,
    *,
    account=None,
    strategy: WarmupStrategy,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    now: datetime = datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
    status: str | None = None,
) -> WarmupSession:
    """Create a warmup session, optionally seeding a new account."""
    if account is None:
        account = seed_warmup_account(db_session, workspace_id=workspace_id)
    ws = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=workspace_id,
        now=now,
    )
    if status is not None:
        ws.status = status
        db_session.commit()
    return ws


def seed_warmup_session_raw(
    db_session,
    account_id: str,
    strategy_id: str,
    status: str,
    *,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
) -> WarmupSession:
    """Low-level session seed without create_warmup_session service call."""
    warmup_session = WarmupSession(
        id=new_id(),
        workspace_id=workspace_id,
        account_id=account_id,
        strategy_id=strategy_id,
        status=status,
        current_day=4,
        cadence_hours=24,
    )
    db_session.add(warmup_session)
    db_session.commit()
    return warmup_session
