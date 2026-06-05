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
        return repository.mark_action_done(
            session,
            warmup_session.workspace_id,
            warmup_session.account_id,
            channel_ref,
            action_type,
            now=timestamp,
            metadata=result.metadata,
        )
    return repository.mark_action_failed(
        session,
        warmup_session.workspace_id,
        warmup_session.account_id,
        channel_ref,
        now=timestamp,
    )
