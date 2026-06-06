from __future__ import annotations

import random
from datetime import UTC, datetime

from sqlalchemy import select

from app.adapters.warmup_tdlib import MockWarmupTdlibAdapter
from app.models import WarmupChannelState, WarmupExecutionMode
from app.modules.warmup.channel_state import repository as channel_state_repository
from app.services.warmup_dispatch import process_due_warmup_dispatches
from tests.helpers.warmup import seed_warmup_session, seed_warmup_strategy


NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


def test_view_story_requires_subscription_and_records_channel_state(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.PASSIVE.value,
        target_channels=[{"username": "@news"}],
        daily_action_limits={"1": {"view_story": 1}},
    )
    warmup_session = seed_warmup_session(db_session, strategy=strategy, now=NOW)
    channel_state_repository.upsert_subscribed(
        db_session,
        warmup_session.workspace_id,
        warmup_session.account_id,
        "@news",
        now=NOW,
    )
    channel_state_repository.update_capabilities(
        db_session,
        warmup_session.workspace_id,
        warmup_session.account_id,
        "@news",
        has_stories=True,
        has_reactions=None,
        available_reactions=(),
        now=NOW,
    )
    adapter = MockWarmupTdlibAdapter(rng_seed=5)

    process_due_warmup_dispatches(
        db_session,
        worker_id="w1",
        now=NOW,
        rng=random.Random(0),
        passive_adapter=adapter,
    )

    story_calls = [call for call in adapter.calls if call["action_type"] == "view_story"]
    assert len(story_calls) == 1
    assert story_calls[0]["context"]["channel_ref"] == "@news"
    state = db_session.execute(select(WarmupChannelState)).scalar_one()
    assert state.last_story_view_at is not None
    assert state.success_count == 1


def test_view_story_skips_when_not_subscribed(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.PASSIVE.value,
        target_channels=[{"username": "@news"}],
        daily_action_limits={"1": {"view_story": 1}},
    )
    warmup_session = seed_warmup_session(db_session, strategy=strategy, now=NOW)
    adapter = MockWarmupTdlibAdapter()

    process_due_warmup_dispatches(
        db_session,
        worker_id="w1",
        now=NOW,
        rng=random.Random(0),
        passive_adapter=adapter,
    )

    skip_events = [
        event
        for event in warmup_session.events
        if event.event_type == "task_skipped"
        and event.payload_json.get("reason") == "not_subscribed"
    ]
    assert skip_events
    assert [call for call in adapter.calls if call["action_type"] == "view_story"] == []
