"""Phase 0a: snapshot-поведение `create_warmup_session`.

Гарантирует, что в момент создания сессия фиксирует:
- `execution_mode` и `duration_days` из выбранной стратегии,
- безопасный `proxy_snapshot_json` из текущего AccountProxy без credentials,
- что эти поля корректно прокинуты в Pydantic-схему `WarmupSessionRead`.
"""

from __future__ import annotations

from app.models import (
    AccountProxy,
    AccountRuntimeState,
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    ProxyCategory,
    WarmupExecutionMode,
    WarmupPresetKind,
    WarmupStrategy,
    new_id,
)
from app.services.accounts import create_account
from app.services.warmup import create_warmup_session


def _seed_account(db_session, *, with_proxy: bool, proxy_category: str = ProxyCategory.RESIDENTIAL.value):
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
    if with_proxy:
        account.proxy = AccountProxy(
            account_id=account.id,
            proxy_type="socks5",
            proxy_category=proxy_category,
            host="127.0.0.1",
            port=1080,
            username="user",
            password_encrypted=None,
            status="ok",
        )
    db_session.commit()
    return account


def _seed_strategy(db_session) -> WarmupStrategy:
    strategy = WarmupStrategy(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        name=f"Стратегия {new_id()[:8]}",
        description="Тестовая стратегия",
        tier_limits_json={"cadence_hours": 24, "profile_required": True},
        target_channels_json=[],
        is_preset=True,
        execution_mode=WarmupExecutionMode.DRY_RUN.value,
        preset_kind=WarmupPresetKind.STANDARD.value,
        duration_days=14,
        daily_action_limits_json={"1": {"feed_read": 5, "join_chat": 0, "p2p_send": 0}},
        session_window_config_json={"micro_sessions_per_day": {"min": 3, "max": 6}},
        ui_summary_json={"audience_hint": "Стандарт"},
    )
    db_session.add(strategy)
    db_session.commit()
    return strategy


def test_create_warmup_session_snapshots_strategy_and_proxy(db_session) -> None:
    account = _seed_account(db_session, with_proxy=True)
    strategy = _seed_strategy(db_session)

    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert warmup_session.execution_mode == WarmupExecutionMode.DRY_RUN.value
    assert warmup_session.duration_days == 14
    snapshot = warmup_session.proxy_snapshot_json
    assert snapshot is not None
    assert snapshot["proxy_category"] == ProxyCategory.RESIDENTIAL.value
    assert snapshot["proxy_type"] == "socks5"
    assert snapshot["host"] == "127.0.0.1"
    assert snapshot["port"] == 1080
    # Никаких credentials в snapshot быть не должно.
    assert "password" not in snapshot
    assert "password_encrypted" not in snapshot
    assert "username" not in snapshot


def test_create_warmup_session_without_proxy_snapshot_is_none(db_session) -> None:
    account = _seed_account(db_session, with_proxy=False)
    strategy = _seed_strategy(db_session)

    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert warmup_session.proxy_snapshot_json is None


def test_create_warmup_session_emits_snapshot_event(db_session) -> None:
    account = _seed_account(db_session, with_proxy=True)
    strategy = _seed_strategy(db_session)

    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    db_session.refresh(warmup_session)
    events = list(warmup_session.events)
    assert events, "session_created event must be emitted"
    payload = events[0].payload_json
    assert payload["execution_mode"] == WarmupExecutionMode.DRY_RUN.value
    assert payload["duration_days"] == 14
    assert payload["proxy_snapshot"]["proxy_category"] == ProxyCategory.RESIDENTIAL.value
    assert (
        payload["personality_seed"]["typing_speed_cps"]
        == (warmup_session.personality_seed_json["typing_speed_cps"])
    )
    assert (
        payload["personality_seed"]["favorite_emojis"]
        == (warmup_session.personality_seed_json["favorite_emojis"])
    )
    assert "action_preferences" not in payload["personality_seed"]


def test_create_warmup_session_applies_mobile_proxy_adaptation(db_session) -> None:
    account = _seed_account(db_session, with_proxy=True, proxy_category=ProxyCategory.MOBILE.value)
    strategy = _seed_strategy(db_session)

    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert set(warmup_session.disabled_actions_json) == {
        "scroll_channels",
        "watch_video",
        "listen_voice",
        "search_gif",
        "view_stickers",
        "link_preview",
    }
    event = next(item for item in warmup_session.events if item.event_type == "proxy_adaptation_applied")
    assert event.payload_json["proxy_category"] == ProxyCategory.MOBILE.value
    assert event.payload_json["applied_preset"] == "economic"
    assert set(event.payload_json["disabled_actions"]) == set(warmup_session.disabled_actions_json)


def test_create_warmup_session_leaves_datacenter_actions_enabled(db_session) -> None:
    account = _seed_account(
        db_session,
        with_proxy=True,
        proxy_category=ProxyCategory.DATACENTER.value,
    )
    strategy = _seed_strategy(db_session)

    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert warmup_session.disabled_actions_json == []
    event = next(item for item in warmup_session.events if item.event_type == "proxy_adaptation_applied")
    assert event.payload_json["applied_preset"] == "full"
