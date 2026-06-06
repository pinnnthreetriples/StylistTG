from __future__ import annotations

import random
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.warmup_tdlib import MockWarmupTdlibAdapter
from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    WarmupChannelState,
    WarmupExecutionMode,
    WarmupSession,
    WarmupStatus,
    new_id,
)
from app.services.warmup_dispatch import process_due_warmup_dispatches
from tests.helpers.warmup import seed_warmup_account, seed_warmup_strategy


NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


def test_inflight_session_survives_advanced_warmup_rollout(db_session: Session) -> None:
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

    assert db_session.execute(select(WarmupChannelState)).scalars().all() == []

    adapter = MockWarmupTdlibAdapter(rng_seed=11)
    rng = random.Random(0)
    for _ in range(60):
        process_due_warmup_dispatches(
            db_session,
            worker_id="compat-worker",
            now=NOW,
            rng=rng,
            passive_adapter=adapter,
        )
        db_session.refresh(warmup_session)
        if warmup_session.status == WarmupStatus.COMPLETED.value:
            break
        warmup_session.next_micro_session_at = NOW
        warmup_session.next_step_at = NOW
        db_session.commit()

    db_session.refresh(warmup_session)
    action_types = [call["action_type"] for call in adapter.calls]
    event_payloads = [event.payload_json for event in warmup_session.events]

    assert warmup_session.status == WarmupStatus.COMPLETED.value
    assert warmup_session.cold_soak_until is None
    assert warmup_session.lifecycle_state == "warming"
    assert "feed_read" in action_types
    assert "join_chat" in action_types
    assert "view_story" not in action_types
    assert "react_to_post" not in action_types
    assert all(payload.get("action_type") != "view_story" for payload in event_payloads)
    assert all(payload.get("action_type") != "react_to_post" for payload in event_payloads)
    assert all(event.event_type != "cold_soak_started" for event in warmup_session.events)
