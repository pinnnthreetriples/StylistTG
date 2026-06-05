from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.adapters.warmup_tdlib import WarmupActionResult
from app.models import WarmupSession, utc_now
from app.modules.warmup.channel_state import repository
from app.modules.warmup.channel_state.contracts import (
    ChannelCapabilities,
    ChannelCapabilitiesAdapter,
    ChannelStateSnapshot,
)
from app.modules.warmup.events import write_warmup_event


def discover_capabilities(
    session: Session,
    adapter: ChannelCapabilitiesAdapter,
    *,
    workspace_id: str,
    account_id: str,
    channel_ref: str,
    now: datetime | None = None,
) -> ChannelCapabilities:
    capabilities = adapter.discover_channel_capabilities(
        account_id=account_id,
        channel_ref=channel_ref,
    )
    repository.update_capabilities(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        channel_ref=channel_ref,
        has_stories=capabilities.has_stories,
        has_reactions=capabilities.has_reactions,
        available_reactions=capabilities.available_reactions,
        now=now or utc_now(),
    )
    return capabilities


def record_action_result(
    session: Session,
    warmup_session: WarmupSession,
    action_type: str,
    channel_ref: str,
    result: WarmupActionResult,
    *,
    now: datetime | None = None,
) -> ChannelStateSnapshot:
    timestamp = now or utc_now()
    if result.is_ok:
        update = repository.mark_channel_success(
            session,
            warmup_session.workspace_id,
            warmup_session.account_id,
            channel_ref,
            action_type=action_type,
            now=timestamp,
            metadata=result.metadata,
        )
    else:
        update = repository.mark_channel_failure(
            session,
            warmup_session.workspace_id,
            warmup_session.account_id,
            channel_ref,
            now=timestamp,
        )
    if update.crossed_blacklist_threshold:
        write_warmup_event(
            session,
            warmup_session,
            "channel_blacklisted",
            {
                "day": warmup_session.current_day,
                "channel_ref": channel_ref,
                "health_score": update.snapshot.health_score,
                "success_count": update.snapshot.success_count,
                "fail_count": update.snapshot.fail_count,
            },
        )
    return update.snapshot
