from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WarmupChannelState
from app.modules.warmup.channel_state import repository


WORKSPACE_ID = "11111111-1111-4111-8111-111111111111"
ACCOUNT_ID = "22222222-2222-4222-8222-222222222222"
OTHER_ACCOUNT_ID = "33333333-3333-4333-8333-333333333333"
NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


def test_upsert_subscribed_is_idempotent(db_session: Session) -> None:
    first = repository.upsert_subscribed(db_session, WORKSPACE_ID, ACCOUNT_ID, "channel-a", now=NOW)
    second = repository.upsert_subscribed(
        db_session, WORKSPACE_ID, ACCOUNT_ID, "channel-a", now=NOW + timedelta(minutes=5)
    )

    rows = db_session.execute(select(WarmupChannelState)).scalars().all()

    assert len(rows) == 1
    assert _without_tz(first.subscribed_at) == _without_tz(NOW)
    assert _without_tz(second.subscribed_at) == _without_tz(NOW)


def test_get_states_for_account_returns_requested_existing_refs_in_input_order(
    db_session: Session,
) -> None:
    repository.mark_action_done(
        db_session, WORKSPACE_ID, ACCOUNT_ID, "channel-b", "feed_read", now=NOW
    )
    repository.mark_action_done(
        db_session,
        WORKSPACE_ID,
        ACCOUNT_ID,
        "channel-a",
        "channel_browse",
        now=NOW + timedelta(minutes=1),
    )
    repository.mark_action_done(
        db_session, WORKSPACE_ID, OTHER_ACCOUNT_ID, "channel-b", "feed_read", now=NOW
    )

    snapshots = repository.get_states_for_account(
        db_session,
        WORKSPACE_ID,
        ACCOUNT_ID,
        ["missing", "channel-a", "channel-b", "channel-a"],
    )

    assert [snapshot.channel_ref for snapshot in snapshots] == ["channel-a", "channel-b"]
    assert _without_tz(snapshots[0].last_browse_at) == _without_tz(NOW + timedelta(minutes=1))
    assert _without_tz(snapshots[1].last_feed_read_at) == _without_tz(NOW)


def test_get_states_for_account_returns_empty_for_empty_refs(db_session: Session) -> None:
    repository.mark_action_done(
        db_session, WORKSPACE_ID, ACCOUNT_ID, "channel-a", "feed_read", now=NOW
    )

    snapshots = repository.get_states_for_account(db_session, WORKSPACE_ID, ACCOUNT_ID, [])

    assert snapshots == []


def test_update_capabilities_upserts_and_persists_reaction_list(db_session: Session) -> None:
    snapshot = repository.update_capabilities(
        db_session,
        WORKSPACE_ID,
        ACCOUNT_ID,
        "channel-a",
        has_stories=True,
        has_reactions=True,
        available_reactions=("👍", "🔥"),
        now=NOW,
    )

    assert snapshot.has_stories is True
    assert snapshot.has_reactions is True
    assert snapshot.available_reactions == ("👍", "🔥")


def test_mark_action_done_updates_matching_timestamp_only(db_session: Session) -> None:
    snapshot = repository.mark_action_done(
        db_session,
        WORKSPACE_ID,
        ACCOUNT_ID,
        "channel-a",
        "react_to_post",
        now=NOW,
    )

    assert _without_tz(snapshot.last_react_at) == _without_tz(NOW)
    assert snapshot.last_feed_read_at is None
    assert snapshot.last_story_view_at is None
    assert snapshot.last_browse_at is None


def _without_tz(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=None)
