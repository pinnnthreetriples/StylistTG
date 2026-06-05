from __future__ import annotations

import random
from datetime import UTC, datetime

from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    WarmupEvent,
    WarmupExecutionMode,
    WarmupSession,
    WarmupStrategy,
)
from app.modules.warmup.adaptive_plan import (
    apply_plan_adjustment,
    compute_next_day_adjustment,
    describe_next_day_adjustment,
)
from app.modules.warmup.dispatch_schedule import _resolve_day_plan
from app.services.warmup_dispatch import process_due_warmup_dispatches
from tests.helpers.warmup import seed_warmup_session, seed_warmup_strategy

NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


def test_compute_next_day_adjustment_accelerates_after_three_clean_days() -> None:
    warmup_session = _session(
        current_day=3,
        counters={
            "0": {"feed_read": 1},
            "1": {"feed_read": 1},
            "2": {"feed_read": 1},
        },
    )

    adjustment = describe_next_day_adjustment(warmup_session)

    assert compute_next_day_adjustment(warmup_session, NOW)["feed_read"] == 1.2
    assert adjustment.reason == "3_clean_days"
    assert adjustment.event_type == "plan_adjusted_up"


def test_compute_next_day_adjustment_slows_down_after_failures() -> None:
    warmup_session = _session(
        current_day=3,
        counters={
            "0": {"feed_read": 1},
            "1": {"failures": 1},
            "2": {"feed_read": 1},
        },
    )

    adjustment = describe_next_day_adjustment(warmup_session)

    assert adjustment.multipliers["feed_read"] == 0.5
    assert adjustment.reason == "recent_failures"
    assert adjustment.event_type == "plan_adjusted_down"


def test_compute_next_day_adjustment_prioritizes_flood_wait_reason() -> None:
    warmup_session = _session(
        current_day=3,
        counters={
            "0": {"feed_read": 1},
            "1": {"failures": 1, "flood_waits": 1},
            "2": {"feed_read": 1},
        },
    )

    adjustment = describe_next_day_adjustment(warmup_session)

    assert adjustment.multipliers["feed_read"] == 0.5
    assert adjustment.reason == "flood_wait"


def test_adaptive_plan_is_neutral_until_three_days_and_off_by_default() -> None:
    warmup_session = _session(current_day=2, counters={"0": {}, "1": {}})
    disabled = _session(current_day=3, counters={"0": {}, "1": {}, "2": {}}, adaptive=False)

    assert compute_next_day_adjustment(warmup_session, NOW)["feed_read"] == 1.0
    assert compute_next_day_adjustment(disabled, NOW) == {}
    assert _resolve_day_plan(disabled) == {"feed_read": 10}


def test_resolve_day_plan_applies_multiplier_with_caps() -> None:
    warmup_session = _session(
        current_day=3,
        counters={
            "0": {"feed_read": 1},
            "1": {"feed_read": 1},
            "2": {"feed_read": 1},
        },
    )

    assert _resolve_day_plan(warmup_session) == {"feed_read": 12}
    assert apply_plan_adjustment({"feed_read": 10}, {"feed_read": 9.0}) == {"feed_read": 20}
    assert apply_plan_adjustment({"feed_read": 10}, {"feed_read": 0.1}) == {"feed_read": 3}


def test_dispatch_writes_plan_adjusted_up_event_on_day_advance(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.SHADOW.value,
        duration_days=7,
        daily_action_limits={
            "1": {"feed_read": 1},
            "2": {"feed_read": 1},
            "3": {"feed_read": 1},
            "4": {"feed_read": 10},
        },
    )
    strategy.session_window_config_json = {"adaptive_enabled": True}
    warmup_session = seed_warmup_session(db_session, strategy=strategy, now=NOW)
    warmup_session.current_day = 2
    warmup_session.daily_counters_json = {
        "0": {"feed_read": 1},
        "1": {"feed_read": 1},
    }
    db_session.commit()

    processed = process_due_warmup_dispatches(
        db_session,
        worker_id="worker-1",
        now=NOW,
        rng=random.Random(0),
    )

    assert processed == 1
    db_session.refresh(warmup_session)
    assert warmup_session.current_day == 3
    assert _resolve_day_plan(warmup_session) == {"feed_read": 12}
    events = db_session.query(WarmupEvent).filter_by(event_type="plan_adjusted_up").all()
    assert events
    assert events[-1].payload_json["multiplier"] == 1.2
    assert events[-1].payload_json["reason"] == "3_clean_days"


def _session(
    *,
    current_day: int,
    counters: dict,
    adaptive: bool = True,
) -> WarmupSession:
    strategy = WarmupStrategy(
        id="11111111-1111-4111-8111-111111111111",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        name="Adaptive",
        is_preset=False,
        execution_mode=WarmupExecutionMode.SHADOW.value,
        duration_days=7,
        daily_action_limits_json={
            "1": {"feed_read": 10},
            "2": {"feed_read": 10},
            "3": {"feed_read": 10},
            "4": {"feed_read": 10},
        },
        session_window_config_json={"adaptive_enabled": adaptive},
    )
    return WarmupSession(
        id="22222222-2222-4222-8222-222222222222",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_id="33333333-3333-4333-8333-333333333333",
        strategy_id=strategy.id,
        strategy=strategy,
        status="active",
        current_day=current_day,
        cadence_hours=24,
        daily_counters_json=counters,
    )
