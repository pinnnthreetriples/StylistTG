from __future__ import annotations

import random
from datetime import UTC, datetime

from app.adapters.warmup_tdlib import MockWarmupTdlibAdapter
from app.models import WarmupExecutionMode
from app.modules.warmup.channel_state import repository as channel_state_repository
from app.services.warmup_dispatch import process_due_warmup_dispatches
from tests.helpers.warmup import seed_warmup_session, seed_warmup_strategy


NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


def test_channel_browse_uses_strategy_target_and_executes_mock(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.PASSIVE.value,
        target_channels=[{"username": "@news"}],
        daily_action_limits={"1": {"channel_browse": 1}},
    )
    warmup_session = seed_warmup_session(db_session, strategy=strategy, now=NOW)
    channel_state_repository.upsert_subscribed(
        db_session,
        warmup_session.workspace_id,
        warmup_session.account_id,
        "@news",
        now=NOW,
    )
    adapter = MockWarmupTdlibAdapter(rng_seed=3)

    processed = process_due_warmup_dispatches(
        db_session,
        worker_id="w1",
        now=NOW,
        rng=random.Random(0),
        passive_adapter=adapter,
    )

    assert processed == 1
    browse_calls = [call for call in adapter.calls if call["action_type"] == "channel_browse"]
    assert len(browse_calls) == 1
    assert browse_calls[0]["context"]["channel_ref"] == "@news"
    assert warmup_session.daily_counters_json.get("0", {}).get("channel_browse") == 1


def test_channel_browse_skips_without_strategy_or_pool_target(db_session) -> None:
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.PASSIVE.value,
        target_channels=[],
        daily_action_limits={"1": {"channel_browse": 1}},
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
        and event.payload_json.get("reason") == "no_browse_target_available"
    ]
    assert skip_events
    assert [call for call in adapter.calls if call["action_type"] == "channel_browse"] == []
