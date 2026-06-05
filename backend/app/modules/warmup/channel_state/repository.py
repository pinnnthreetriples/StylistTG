from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WarmupChannelState
from app.modules.warmup.channel_state.contracts import ChannelStateSnapshot

_ACTION_TIMESTAMP_COLUMNS: dict[str, str] = {
    "feed_read": "last_feed_read_at",
    "view_story": "last_story_view_at",
    "react_to_post": "last_react_at",
    "channel_browse": "last_browse_at",
    "join_chat": "subscribed_at",
}


def get_states_for_account(
    session: Session,
    workspace_id: str,
    account_id: str,
    channel_refs: list[str],
) -> list[ChannelStateSnapshot]:
    refs = list(dict.fromkeys(channel_refs))
    if not refs:
        return []
    rows = session.execute(
        select(WarmupChannelState).where(
            WarmupChannelState.workspace_id == workspace_id,
            WarmupChannelState.account_id == account_id,
            WarmupChannelState.channel_ref.in_(refs),
        )
    ).scalars()
    by_ref = {row.channel_ref: _snapshot(row) for row in rows}
    return [by_ref[channel_ref] for channel_ref in refs if channel_ref in by_ref]


def upsert_subscribed(
    session: Session,
    workspace_id: str,
    account_id: str,
    channel_ref: str,
    *,
    now: datetime,
) -> ChannelStateSnapshot:
    row = _get_or_create_state(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        channel_ref=channel_ref,
        now=now,
    )
    if row.subscribed_at is None:
        row.subscribed_at = now
    row.updated_at = now
    session.flush()
    return _snapshot(row)


def mark_action_done(
    session: Session,
    workspace_id: str,
    account_id: str,
    channel_ref: str,
    action_type: str,
    *,
    now: datetime,
    metadata: dict[str, Any] | None = None,
) -> ChannelStateSnapshot:
    del metadata
    row = _get_or_create_state(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        channel_ref=channel_ref,
        now=now,
    )
    column_name = _ACTION_TIMESTAMP_COLUMNS.get(action_type)
    if column_name is not None:
        setattr(row, column_name, now)
    row.success_count += 1
    row.updated_at = now
    session.flush()
    return _snapshot(row)


def mark_action_failed(
    session: Session,
    workspace_id: str,
    account_id: str,
    channel_ref: str,
    *,
    now: datetime,
) -> ChannelStateSnapshot:
    row = _get_or_create_state(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        channel_ref=channel_ref,
        now=now,
    )
    row.fail_count += 1
    row.updated_at = now
    session.flush()
    return _snapshot(row)


def update_capabilities(
    session: Session,
    workspace_id: str,
    account_id: str,
    channel_ref: str,
    *,
    has_stories: bool | None,
    has_reactions: bool | None,
    available_reactions: tuple[str, ...],
    now: datetime,
) -> ChannelStateSnapshot:
    row = _get_or_create_state(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        channel_ref=channel_ref,
        now=now,
    )
    row.has_stories = has_stories
    row.has_reactions = has_reactions
    row.available_reactions_json = list(available_reactions)
    row.updated_at = now
    session.flush()
    return _snapshot(row)


def _get_or_create_state(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    channel_ref: str,
    now: datetime,
) -> WarmupChannelState:
    row = session.execute(
        select(WarmupChannelState).where(
            WarmupChannelState.workspace_id == workspace_id,
            WarmupChannelState.account_id == account_id,
            WarmupChannelState.channel_ref == channel_ref,
        )
    ).scalar_one_or_none()
    if row is not None:
        return row
    row = WarmupChannelState(
        workspace_id=workspace_id,
        account_id=account_id,
        channel_ref=channel_ref,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return row


def _snapshot(row: WarmupChannelState) -> ChannelStateSnapshot:
    return ChannelStateSnapshot(
        channel_ref=row.channel_ref,
        subscribed_at=row.subscribed_at,
        last_feed_read_at=row.last_feed_read_at,
        last_story_view_at=row.last_story_view_at,
        last_react_at=row.last_react_at,
        last_browse_at=row.last_browse_at,
        has_stories=row.has_stories,
        has_reactions=row.has_reactions,
        available_reactions=tuple(row.available_reactions_json or ()),
        health_score=row.health_score,
    )
