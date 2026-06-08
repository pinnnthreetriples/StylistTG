from __future__ import annotations

from datetime import UTC, datetime, timedelta
import random
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.warmup_tdlib import MockWarmupTdlibAdapter
from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    ProxyCategory,
    WarmupEvent,
    WarmupExecutionMode,
    WarmupP2pFriendLink,
    WarmupPreProductionSession,
    WarmupSession,
    WarmupStatus,
    WarmupTrustedPeer,
    new_id,
)
from app.modules.account_lifecycle.interfaces import AccountLifecycleState
from app.modules.warmup import pre_production
from app.modules.warmup.adaptive_plan import describe_next_day_adjustment
from app.modules.warmup.channel_state.contracts import ChannelStateSnapshot
from app.modules.warmup.channel_state.health import HEALTH_THRESHOLD_EXCLUDE, compute_health_score
from app.modules.warmup.channel_state.selector import choose_actions
from app.modules.warmup.circadian.personality import generate_personality_seed
from app.modules.warmup.circadian.windows import hour_weight, pick_next_window
from app.modules.warmup.cyclic import compute_total_active_hours, setup_cyclic_warmup
from app.modules.warmup.idle_session import run_idle_warmup_sweep
from app.modules.warmup.p2p import select_eligible_peer
from app.modules.warmup.pre_production import complete_due_pre_production_sessions
from app.modules.warmup.proxy_adaptation import compute_disabled_actions_for_proxy
from app.services.warmup import create_warmup_session
from app.services.warmup_dispatch import process_due_warmup_dispatches
from tests.helpers.warmup import seed_warmup_account, seed_warmup_strategy

NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


class _AlwaysSelectRandom(random.Random):
    def random(self) -> float:
        return 0.0


def test_full_lifecycle_express(db_session: Session, monkeypatch) -> None:
    warmup_session = _run_shadow_lifecycle(
        db_session,
        monkeypatch,
        duration_days=7,
        preset_kind="express",
    )

    assert warmup_session.status == WarmupStatus.COMPLETED.value
    assert warmup_session.duration_days == 7
    assert warmup_session.account.lifecycle_state == AccountLifecycleState.PRE_PRODUCTION.value


def test_full_lifecycle_standard(db_session: Session, monkeypatch) -> None:
    warmup_session = _run_shadow_lifecycle(
        db_session,
        monkeypatch,
        duration_days=14,
        preset_kind="standard",
    )

    assert warmup_session.status == WarmupStatus.COMPLETED.value
    assert warmup_session.duration_days == 14
    assert "completed" in _event_types(db_session, warmup_session.id)


def test_full_lifecycle_hardened(db_session: Session, monkeypatch) -> None:
    warmup_session = _run_shadow_lifecycle(
        db_session,
        monkeypatch,
        duration_days=21,
        preset_kind="hardened",
    )

    assert warmup_session.status == WarmupStatus.COMPLETED.value
    assert warmup_session.duration_days == 21
    assert warmup_session.current_day == 21


def test_cold_soak_to_warming_transition(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(pre_production.settings, "warmup_pre_production_enabled", False)
    monkeypatch.setattr("app.modules.warmup.cold_soak.settings.warmup_cold_soak_min_hours", 12)
    monkeypatch.setattr("app.modules.warmup.cold_soak.settings.warmup_cold_soak_max_hours", 12)
    account = seed_warmup_account(db_session)
    strategy = _seed_shadow_strategy(db_session, duration_days=3)
    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=account.workspace_id,
        now=NOW,
    )
    warmup_session.cold_soak_until = NOW
    warmup_session.next_micro_session_at = None
    warmup_session.next_step_at = NOW
    db_session.commit()

    due = process_due_warmup_dispatches(
        db_session,
        worker_id="worker-1",
        now=NOW,
        rng=_AlwaysSelectRandom(0),
    )

    db_session.refresh(warmup_session)
    assert due == 1
    assert account.lifecycle_state == AccountLifecycleState.WARMING.value
    assert "cold_soak_completed" in _event_types(db_session, warmup_session.id)


def test_warming_to_pre_production_to_active(db_session: Session, monkeypatch) -> None:
    _disable_cold_soak(monkeypatch)
    monkeypatch.setattr(pre_production.settings, "warmup_pre_production_enabled", True)
    monkeypatch.setattr(pre_production.settings, "warmup_pre_production_duration_hours", 1)
    account = seed_warmup_account(db_session)
    strategy = _seed_shadow_strategy(db_session, duration_days=3)
    strategy.tier_limits_json = {"enable_pre_production": True}
    strategy.target_channels_json = [{"channel_ref": "@safe"}]
    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=account.workspace_id,
        now=NOW,
    )
    db_session.commit()

    _drive_due_session_to_completion(db_session, warmup_session)
    preprod = db_session.scalar(
        select(WarmupPreProductionSession).where(
            WarmupPreProductionSession.account_id == account.id
        )
    )
    processed = complete_due_pre_production_sessions(
        db_session,
        workspace_id=account.workspace_id,
        now=preprod.ends_at + timedelta(seconds=1),
    )

    assert preprod is not None
    assert preprod.status == "completed"
    assert processed == 1
    assert account.lifecycle_state == AccountLifecycleState.ACTIVE.value
    assert "pre_production_started" in _event_types(db_session, warmup_session.id)


def test_idle_warmup_kicks_in_after_inactivity(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    account.lifecycle_state = AccountLifecycleState.ACTIVE.value
    db_session.commit()

    processed = run_idle_warmup_sweep(
        db_session,
        workspace_id=account.workspace_id,
        now=NOW,
        config=SimpleNamespace(
            warmup_idle_detection_enabled=True,
            warmup_idle_threshold_minutes=60,
        ),
    )
    row = db_session.scalar(select(WarmupSession).where(WarmupSession.account_id == account.id))

    assert processed == 1
    assert account.lifecycle_state == AccountLifecycleState.IDLE.value
    assert row is not None
    assert row.lifecycle_state == "idle"
    assert "p2p_send" in row.disabled_actions_json


def test_cyclic_mode_7_days(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    seed_warmup_strategy(db_session, is_preset=True, duration_days=7)

    warmup_session = setup_cyclic_warmup(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        start_hour=15,
        end_hour=18,
        days_total=7,
        strategy_preset="standard",
        now=NOW,
    )

    assert warmup_session.duration_days == 7
    assert compute_total_active_hours(warmup_session.cycle_config_json) == 21
    assert "cyclic.started" in _event_types(db_session, warmup_session.id)


def test_friend_graph_p2p_isolation(db_session: Session, monkeypatch) -> None:
    _disable_cold_soak(monkeypatch)
    sender = seed_warmup_account(db_session, telegram_user_id="100")
    friends = [
        _seed_trusted_peer(db_session, telegram_user_id=str(200 + index)) for index in range(4)
    ]
    strategy = _seed_shadow_strategy(db_session, duration_days=3)

    warmup_session = create_warmup_session(
        db_session,
        account_id=sender.id,
        strategy_id=strategy.id,
        workspace_id=sender.workspace_id,
        now=NOW,
    )
    non_friend = _seed_trusted_peer(db_session, telegram_user_id="999")
    selected = select_eligible_peer(
        db_session,
        workspace_id=sender.workspace_id,
        sender_account_id=sender.id,
        now=NOW + timedelta(days=2),
    )

    linked_ids = {
        link.friend_account_id
        for link in db_session.execute(
            select(WarmupP2pFriendLink).where(WarmupP2pFriendLink.account_id == sender.id)
        ).scalars()
    }
    assert len(linked_ids) == 3
    assert linked_ids.issubset({friend.id for friend in friends})
    assert non_friend.id not in linked_ids
    assert selected is not None
    assert selected.account_id in linked_ids
    assert warmup_session.id


def test_personality_seed_determinism(db_session: Session, monkeypatch) -> None:
    _disable_cold_soak(monkeypatch)
    account = seed_warmup_account(db_session)
    strategy = _seed_shadow_strategy(db_session, duration_days=3)

    first = generate_personality_seed(account.id)
    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=account.workspace_id,
        now=NOW,
    )

    assert warmup_session.personality_seed_json == first
    assert generate_personality_seed(account.id) == first


def test_circadian_distribution() -> None:
    seed = {"account_id": "account-1", "preferred_hours": [19]}
    next_window = pick_next_window(
        datetime(2026, 6, 5, 6, 0, tzinfo=UTC),
        "UTC",
        rng=_AlwaysSelectRandom(0),
        personality_seed=seed,
    )

    assert hour_weight(19, personality_seed=seed) > hour_weight(15, personality_seed=seed)
    assert 7 <= next_window.hour <= 22


def test_adaptive_plan_speedup_on_clean_days(db_session: Session) -> None:
    warmup_session = _seed_adaptive_session(
        db_session,
        counters={"0": {"feed_read": 1}, "1": {"feed_read": 1}, "2": {"feed_read": 1}},
    )

    adjustment = describe_next_day_adjustment(warmup_session)

    assert adjustment.event_type == "plan_adjusted_up"
    assert adjustment.reason == "3_clean_days"
    assert adjustment.multiplier == 1.2


def test_adaptive_plan_slowdown_on_flood_wait(db_session: Session) -> None:
    warmup_session = _seed_adaptive_session(
        db_session,
        counters={"0": {"feed_read": 1}, "1": {"failures": 1, "flood_waits": 1}, "2": {}},
    )

    adjustment = describe_next_day_adjustment(warmup_session)

    assert adjustment.event_type == "plan_adjusted_down"
    assert adjustment.reason == "flood_wait"
    assert adjustment.multiplier == 0.5


def test_channel_health_blacklists_dead_channel() -> None:
    selected = choose_actions(
        plan={"channel_browse": 1},
        counters={},
        channel_states=[
            _channel_state("@dead", health_score=HEALTH_THRESHOLD_EXCLUDE - 0.01),
            _channel_state("@healthy", health_score=1.0),
        ],
        available_targets=["@dead", "@healthy"],
        rng=_AlwaysSelectRandom(0),
        now=NOW,
    )

    assert [action.channel_ref for action in selected] == ["@healthy"]
    assert compute_health_score(0, 3, None, NOW) < HEALTH_THRESHOLD_EXCLUDE


def test_proxy_adaptive_economic_for_mobile(db_session: Session, monkeypatch) -> None:
    _disable_cold_soak(monkeypatch)
    account = seed_warmup_account(db_session, proxy_category=ProxyCategory.MOBILE.value)
    strategy = _seed_shadow_strategy(db_session, duration_days=3)

    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=account.workspace_id,
        now=NOW,
    )

    assert set(compute_disabled_actions_for_proxy("mobile")).issubset(
        set(warmup_session.disabled_actions_json)
    )
    event = _latest_event(db_session, warmup_session.id, "proxy_adaptation_applied")
    assert event is not None
    assert event.payload_json["applied_preset"] == "economic"


def test_inflight_session_survives_rollout(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.PASSIVE.value,
        target_channels=[{"username": "@legacy_news"}],
        daily_action_limits={
            "1": {"feed_read": 1},
            "2": {"join_chat": 1},
            "3": {"feed_read": 1},
        },
        duration_days=3,
    )
    warmup_session = WarmupSession(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_id=account.id,
        strategy_id=strategy.id,
        status=WarmupStatus.ACTIVE.value,
        execution_mode=WarmupExecutionMode.PASSIVE.value,
        current_day=0,
        duration_days=3,
        cadence_hours=24,
        next_micro_session_at=NOW,
        next_step_at=NOW,
        cold_soak_until=None,
        personality_seed_json={},
        disabled_actions_json=[],
        lifecycle_state="warming",
        strategy_snapshot_json=None,
        daily_counters_json={},
        trusted_peer_ids_json=[],
        proxy_snapshot_json={},
        created_at=NOW,
        updated_at=NOW,
    )
    db_session.add(warmup_session)
    db_session.commit()
    adapter = MockWarmupTdlibAdapter(rng_seed=11)

    for _ in range(10):
        process_due_warmup_dispatches(
            db_session,
            worker_id="compat-worker",
            now=NOW,
            rng=_AlwaysSelectRandom(0),
            passive_adapter=adapter,
        )
        db_session.refresh(warmup_session)
        if warmup_session.status == WarmupStatus.COMPLETED.value:
            break
        warmup_session.next_micro_session_at = NOW
        warmup_session.next_step_at = NOW
        db_session.commit()

    action_types = [call["action_type"] for call in adapter.calls]
    assert warmup_session.status == WarmupStatus.COMPLETED.value
    assert warmup_session.cold_soak_until is None
    assert "feed_read" in action_types
    assert "join_chat" in action_types
    assert "cold_soak_started" not in _event_types(db_session, warmup_session.id)


def _run_shadow_lifecycle(
    db_session: Session,
    monkeypatch,
    *,
    duration_days: int,
    preset_kind: str,
) -> WarmupSession:
    _disable_cold_soak(monkeypatch)
    monkeypatch.setattr(pre_production.settings, "warmup_pre_production_enabled", False)
    account = seed_warmup_account(db_session)
    strategy = _seed_shadow_strategy(db_session, duration_days=duration_days)
    strategy.preset_kind = preset_kind
    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=account.workspace_id,
        now=NOW,
    )
    db_session.commit()

    now = NOW
    for _ in range(duration_days + 2):
        process_due_warmup_dispatches(
            db_session,
            worker_id="golden-worker",
            now=now,
            rng=_AlwaysSelectRandom(0),
        )
        db_session.refresh(warmup_session)
        if warmup_session.status == WarmupStatus.COMPLETED.value:
            return warmup_session
        now += timedelta(days=1)
        warmup_session.next_micro_session_at = now
        warmup_session.next_step_at = now
        db_session.commit()
    return warmup_session


def _seed_shadow_strategy(db_session: Session, *, duration_days: int):
    return seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.SHADOW.value,
        duration_days=duration_days,
        daily_action_limits={str(day): {"feed_read": 1} for day in range(1, duration_days + 1)},
    )


def _seed_adaptive_session(db_session: Session, *, counters: dict[str, dict[str, int]]):
    strategy = _seed_shadow_strategy(db_session, duration_days=7)
    strategy.session_window_config_json = {"adaptive_enabled": True}
    warmup_session = WarmupSession(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_id=seed_warmup_account(db_session).id,
        strategy_id=strategy.id,
        strategy=strategy,
        status=WarmupStatus.ACTIVE.value,
        execution_mode=WarmupExecutionMode.SHADOW.value,
        current_day=3,
        duration_days=7,
        cadence_hours=24,
        daily_counters_json=counters,
        created_at=NOW,
        updated_at=NOW,
    )
    db_session.add(warmup_session)
    db_session.commit()
    return warmup_session


def _seed_trusted_peer(db_session: Session, *, telegram_user_id: str):
    account = seed_warmup_account(db_session, telegram_user_id=telegram_user_id)
    db_session.add(
        WarmupTrustedPeer(
            id=new_id(),
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            account_id=account.id,
            eligible_from=NOW - timedelta(days=1),
            max_active_contacts=3,
            current_contacts=0,
        )
    )
    db_session.commit()
    return account


def _channel_state(channel_ref: str, *, health_score: float) -> ChannelStateSnapshot:
    return ChannelStateSnapshot(
        channel_ref=channel_ref,
        subscribed_at=NOW - timedelta(days=1),
        last_feed_read_at=None,
        last_story_view_at=None,
        last_react_at=None,
        last_browse_at=None,
        has_stories=True,
        has_reactions=True,
        available_reactions=("+1",),
        health_score=health_score,
    )


def _disable_cold_soak(monkeypatch) -> None:
    monkeypatch.setattr("app.modules.warmup.cold_soak.settings.warmup_cold_soak_min_hours", 0)
    monkeypatch.setattr("app.modules.warmup.cold_soak.settings.warmup_cold_soak_max_hours", 0)


def _drive_due_session_to_completion(
    db_session: Session,
    warmup_session: WarmupSession,
    *,
    start: datetime = NOW,
) -> None:
    now = start
    for _ in range(warmup_session.duration_days + 2):
        process_due_warmup_dispatches(
            db_session,
            worker_id="golden-worker",
            now=now,
            rng=_AlwaysSelectRandom(0),
        )
        db_session.refresh(warmup_session)
        if warmup_session.status == WarmupStatus.COMPLETED.value:
            return
        now += timedelta(days=1)
        warmup_session.next_micro_session_at = now
        warmup_session.next_step_at = now
        db_session.commit()


def _event_types(session: Session, session_id: str) -> list[str]:
    return list(
        session.execute(
            select(WarmupEvent.event_type).where(WarmupEvent.session_id == session_id)
        ).scalars()
    )


def _latest_event(session: Session, session_id: str, event_type: str) -> WarmupEvent | None:
    return session.execute(
        select(WarmupEvent)
        .where(WarmupEvent.session_id == session_id, WarmupEvent.event_type == event_type)
        .order_by(WarmupEvent.created_at.desc(), WarmupEvent.id.desc())
        .limit(1)
    ).scalar_one_or_none()
