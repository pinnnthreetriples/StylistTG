from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WarmupChannelState
from app.modules.warmup.channel_state.contracts import ChannelStateSnapshot
from app.modules.warmup.channel_state.health import (
    HEALTH_THRESHOLD_EXCLUDE,
    compute_health_score,
)

_ACTION_TIMESTAMP_COLUMNS: dict[str, str] = {
    "feed_read": "last_feed_read_at",
    "view_story": "last_story_view_at",
    "react_to_post": "last_react_at",
    "channel_browse": "last_browse_at",
    "scroll_channels": "last_browse_at",
    "join_chat": "subscribed_at",
}


@dataclass(frozen=True)
class ChannelStateUpdate:
    snapshot: ChannelStateSnapshot
    crossed_blacklist_threshold: bool = False


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
    return mark_channel_success(
        session,
        workspace_id,
        account_id,
        channel_ref,
        action_type=action_type,
        now=now,
        metadata=metadata,
    ).snapshot


def mark_channel_success(
    session: Session,
    workspace_id: str,
    account_id: str,
    channel_ref: str,
    *,
    action_type: str,
    now: datetime,
    metadata: dict[str, Any] | None = None,
) -> ChannelStateUpdate:
    row = _get_or_create_state(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        channel_ref=channel_ref,
        now=now,
    )
    previous_health = row.health_score
    column_name = _ACTION_TIMESTAMP_COLUMNS.get(action_type)
    if column_name is not None:
        setattr(row, column_name, now)
    _apply_capability_metadata(row, metadata or {})
    row.success_count += 1
    row.health_score = compute_health_score(row.success_count, row.fail_count, now, now)
    row.updated_at = now
    session.flush()
    return ChannelStateUpdate(
        snapshot=_snapshot(row),
        crossed_blacklist_threshold=_crossed_blacklist_threshold(previous_health, row.health_score),
    )


def mark_action_failed(
    session: Session,
    workspace_id: str,
    account_id: str,
    channel_ref: str,
    *,
    now: datetime,
) -> ChannelStateSnapshot:
    return mark_channel_failure(
        session,
        workspace_id,
        account_id,
        channel_ref,
        now=now,
    ).snapshot


def mark_channel_failure(
    session: Session,
    workspace_id: str,
    account_id: str,
    channel_ref: str,
    *,
    now: datetime,
) -> ChannelStateUpdate:
    row = _get_or_create_state(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        channel_ref=channel_ref,
        now=now,
    )
    previous_health = row.health_score
    row.fail_count += 1
    row.health_score = compute_health_score(
        row.success_count,
        row.fail_count,
        _last_success_at(row),
        now,
    )
    row.updated_at = now
    session.flush()
    return ChannelStateUpdate(
        snapshot=_snapshot(row),
        crossed_blacklist_threshold=_crossed_blacklist_threshold(previous_health, row.health_score),
    )


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


def _apply_capability_metadata(row: WarmupChannelState, metadata: dict[str, Any]) -> None:
    if "has_stories" in metadata:
        row.has_stories = _bool_or_none(metadata.get("has_stories"))
    if "has_reactions" in metadata:
        row.has_reactions = _bool_or_none(metadata.get("has_reactions"))
    if "available_reactions" in metadata:
        raw_reactions = metadata.get("available_reactions")
        row.available_reactions_json = (
            [str(value) for value in cast(list[Any], raw_reactions) if str(value).strip()]
            if isinstance(raw_reactions, list)
            else []
        )


def _bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _last_success_at(row: WarmupChannelState) -> datetime | None:
    values = [
        row.subscribed_at,
        row.last_feed_read_at,
        row.last_story_view_at,
        row.last_react_at,
        row.last_browse_at,
    ]
    return max((value for value in values if value is not None), default=None)


def _crossed_blacklist_threshold(previous_health: float, next_health: float) -> bool:
    return previous_health >= HEALTH_THRESHOLD_EXCLUDE and next_health < HEALTH_THRESHOLD_EXCLUDE


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
        success_count=row.success_count,
        fail_count=row.fail_count,
    )
