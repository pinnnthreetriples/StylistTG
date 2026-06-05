from __future__ import annotations

import random
from datetime import UTC, datetime

from app.models import DEFAULT_LOCAL_WORKSPACE_ID, WarmupExecutionMode
from app.modules.warmup.bootstrap_pool.repository import upsert_channel
from app.services.warmup_dispatch import process_due_warmup_dispatches
from tests.helpers.warmup import (
    seed_warmup_session,
    seed_warmup_strategy,
)


def test_dispatch_uses_bootstrap_pool_when_strategy_has_no_targets(db_session) -> None:
    upsert_channel(
        db_session,
        channel_ref="@bootstrap_join_target",
        category="tech",
        language="en",
        country="US",
    )
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.SHADOW.value,
        target_channels=[],
        daily_action_limits={"1": {"join_chat": 1}},
    )
    warmup_session = seed_warmup_session(db_session, strategy=strategy)
    when = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    warmup_session.next_micro_session_at = when
    warmup_session.next_step_at = when
    db_session.commit()

    processed = process_due_warmup_dispatches(
        db_session,
        worker_id="worker-1",
        now=when,
        rng=random.Random(0),
    )

    assert processed == 1
    db_session.refresh(warmup_session)
    window_events = [
        event for event in warmup_session.events if event.event_type == "micro_session_window_opened"
    ]
    assert window_events
    targets = window_events[-1].payload_json["planned_action_targets"]
    assert targets == [
        {
            "action_type": "join_chat",
            "channel_ref": "@bootstrap_join_target",
            "metadata": {"reason": "not_subscribed"},
        }
    ]
    assert warmup_session.workspace_id == DEFAULT_LOCAL_WORKSPACE_ID
