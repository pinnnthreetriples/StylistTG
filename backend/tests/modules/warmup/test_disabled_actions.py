from __future__ import annotations

import random
from datetime import UTC, datetime

import pytest

from app.models import WarmupEvent, WarmupExecutionMode
from app.modules.warmup.commands import set_disabled_actions
from app.modules.warmup.errors import WarmupSessionRejectedError
from app.services.warmup_dispatch import process_due_warmup_dispatches
from tests.helpers.warmup import seed_warmup_session, seed_warmup_strategy

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


def test_set_disabled_actions_persists_ordered_actions_and_writes_event(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        daily_action_limits={"1": {"feed_read": 1, "react_to_post": 1, "p2p_send": 1}},
    )
    warmup_session = seed_warmup_session(db_session, strategy=strategy, now=NOW)

    updated = set_disabled_actions(
        db_session,
        session_id=warmup_session.id,
        workspace_id=warmup_session.workspace_id,
        actions=["react_to_post", "feed_read", "react_to_post"],
        actor_user_id="operator-1",
        now=NOW,
    )
    db_session.commit()

    assert updated.disabled_actions_json == ["feed_read", "react_to_post"]
    event = db_session.query(WarmupEvent).filter_by(event_type="disabled_actions_updated").one()
    assert event.payload_json["disabled_actions"] == ["feed_read", "react_to_post"]
    assert event.payload_json["actor_user_id"] == "operator-1"


def test_set_disabled_actions_rejects_unknown_action(db_session) -> None:
    strategy = seed_warmup_strategy(db_session, daily_action_limits={"1": {"feed_read": 1}})
    warmup_session = seed_warmup_session(db_session, strategy=strategy, now=NOW)

    with pytest.raises(WarmupSessionRejectedError, match="unknown disabled action"):
        set_disabled_actions(
            db_session,
            session_id=warmup_session.id,
            workspace_id=warmup_session.workspace_id,
            actions=["not_real"],
        )


def test_set_disabled_actions_rejects_disabling_all_planned_actions(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        daily_action_limits={"1": {"feed_read": 1, "react_to_post": 1}},
    )
    warmup_session = seed_warmup_session(db_session, strategy=strategy, now=NOW)

    with pytest.raises(WarmupSessionRejectedError, match="at least one"):
        set_disabled_actions(
            db_session,
            session_id=warmup_session.id,
            workspace_id=warmup_session.workspace_id,
            actions=["feed_read", "react_to_post"],
        )


def test_dispatch_skips_disabled_action_without_incrementing_counter(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.SHADOW.value,
        daily_action_limits={"1": {"feed_read": 1, "react_to_post": 1}},
    )
    warmup_session = seed_warmup_session(db_session, strategy=strategy, now=NOW)
    set_disabled_actions(
        db_session,
        session_id=warmup_session.id,
        workspace_id=warmup_session.workspace_id,
        actions=["feed_read"],
        now=NOW,
    )
    db_session.commit()

    processed = process_due_warmup_dispatches(
        db_session,
        worker_id="worker-1",
        now=NOW,
        rng=random.Random(0),
    )

    assert processed == 1
    db_session.refresh(warmup_session)
    assert warmup_session.daily_counters_json.get("0", {}).get("feed_read", 0) == 0
    skip_events = [
        event
        for event in warmup_session.events
        if event.event_type == "task_skipped"
        and event.payload_json.get("reason") == "disabled_by_operator"
    ]
    assert skip_events
