from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.warmup_tdlib import WarmupActionResult
from app.models import WarmupChannelState, WarmupEvent, WarmupSession
from app.modules.warmup.channel_state.contracts import ChannelCapabilities
from app.modules.warmup.channel_state.service import discover_capabilities, record_action_result


WORKSPACE_ID = "11111111-1111-4111-8111-111111111111"
ACCOUNT_ID = "22222222-2222-4222-8222-222222222222"
NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


@dataclass
class MockChannelCapabilitiesAdapter:
    calls: int = 0

    def discover_channel_capabilities(
        self, *, account_id: str, channel_ref: str
    ) -> ChannelCapabilities:
        self.calls += 1
        assert account_id == ACCOUNT_ID
        return ChannelCapabilities(
            channel_ref=channel_ref,
            has_stories=True,
            has_reactions=False,
            available_reactions=("👍",),
        )


def test_discover_capabilities_uses_adapter_once_and_saves_snapshot(
    db_session: Session,
) -> None:
    adapter = MockChannelCapabilitiesAdapter()

    capabilities = discover_capabilities(
        db_session,
        adapter,
        workspace_id=WORKSPACE_ID,
        account_id=ACCOUNT_ID,
        channel_ref="channel-a",
        now=NOW,
    )
    row = db_session.execute(select(WarmupChannelState)).scalar_one()

    assert adapter.calls == 1
    assert capabilities.channel_ref == "channel-a"
    assert row.has_stories is True
    assert row.has_reactions is False
    assert row.available_reactions_json == ["👍"]


def test_record_action_result_updates_success_timestamp(db_session: Session) -> None:
    warmup_session = _warmup_session()
    result = WarmupActionResult(status="ok", action_type="view_story")

    snapshot = record_action_result(
        db_session,
        warmup_session,
        "view_story",
        "channel-a",
        result,
        now=NOW,
    )
    row = db_session.execute(select(WarmupChannelState)).scalar_one()

    assert _without_tz(snapshot.last_story_view_at) == _without_tz(NOW)
    assert row.success_count == 1
    assert row.fail_count == 0


def test_record_action_result_failure_increments_fail_count_without_last_timestamp(
    db_session: Session,
) -> None:
    warmup_session = _warmup_session()
    result = WarmupActionResult(
        status="failed",
        action_type="react_to_post",
        error_code="REACTIONS_DISABLED",
    )

    snapshot = record_action_result(
        db_session,
        warmup_session,
        "react_to_post",
        "channel-a",
        result,
        now=NOW,
    )
    row = db_session.execute(select(WarmupChannelState)).scalar_one()

    assert snapshot.last_react_at is None
    assert row.success_count == 0
    assert row.fail_count == 1
    assert row.health_score > 0.25


def test_record_action_result_reuses_existing_channel_state(db_session: Session) -> None:
    warmup_session = _warmup_session()
    ok = WarmupActionResult(status="ok", action_type="channel_browse")
    later = NOW + timedelta(minutes=3)

    record_action_result(db_session, warmup_session, "channel_browse", "channel-a", ok, now=NOW)
    record_action_result(db_session, warmup_session, "feed_read", "channel-a", ok, now=later)

    rows = db_session.execute(select(WarmupChannelState)).scalars().all()

    assert len(rows) == 1
    assert _without_tz(rows[0].last_browse_at) == _without_tz(NOW)
    assert _without_tz(rows[0].last_feed_read_at) == _without_tz(later)
    assert rows[0].success_count == 2


def test_record_action_result_updates_capability_metadata(db_session: Session) -> None:
    warmup_session = _warmup_session()
    result = WarmupActionResult(
        status="ok",
        action_type="react_to_post",
        metadata={
            "has_reactions": True,
            "available_reactions": ["👍", "🔥"],
        },
    )

    record_action_result(
        db_session,
        warmup_session,
        "react_to_post",
        "channel-a",
        result,
        now=NOW,
    )
    row = db_session.execute(select(WarmupChannelState)).scalar_one()

    assert row.has_reactions is True
    assert row.available_reactions_json == ["👍", "🔥"]


def test_record_action_result_blacklists_channel_once_below_threshold(
    db_session: Session,
) -> None:
    warmup_session = _warmup_session()
    result = WarmupActionResult(
        status="failed",
        action_type="react_to_post",
        error_code="REACTIONS_DISABLED",
    )

    for _ in range(3):
        record_action_result(
            db_session,
            warmup_session,
            "react_to_post",
            "channel-a",
            result,
            now=NOW,
        )
    record_action_result(
        db_session,
        warmup_session,
        "react_to_post",
        "channel-a",
        result,
        now=NOW,
    )

    row = db_session.execute(select(WarmupChannelState)).scalar_one()
    events = db_session.query(WarmupEvent).filter_by(event_type="channel_blacklisted").all()

    assert row.health_score < 0.25
    assert len(events) == 1
    assert events[0].payload_json["channel_ref"] == "channel-a"
    assert events[0].payload_json["fail_count"] == 3


def test_record_action_result_success_recovers_channel_health(db_session: Session) -> None:
    warmup_session = _warmup_session()
    failed = WarmupActionResult(status="failed", action_type="channel_browse")
    ok = WarmupActionResult(status="ok", action_type="channel_browse")

    for _ in range(3):
        record_action_result(db_session, warmup_session, "channel_browse", "channel-a", failed, now=NOW)
    snapshot = record_action_result(
        db_session,
        warmup_session,
        "channel_browse",
        "channel-a",
        ok,
        now=NOW + timedelta(minutes=1),
    )

    assert snapshot.health_score >= 0.25
    assert snapshot.success_count == 1
    assert snapshot.fail_count == 3


def _warmup_session() -> WarmupSession:
    return WarmupSession(
        id="44444444-4444-4444-8444-444444444444",
        workspace_id=WORKSPACE_ID,
        account_id=ACCOUNT_ID,
        strategy_id="55555555-5555-4555-8555-555555555555",
        status="active",
        current_day=1,
        cadence_hours=24,
    )


def _without_tz(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=None)
