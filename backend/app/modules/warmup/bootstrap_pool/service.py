from __future__ import annotations

import random
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import WarmupBootstrapChannel, WarmupSession, utc_now
from . import repository
from app.modules.warmup.dispatch_context import _target_channel_refs


def list_bootstrap_channels(
    session: Session, *, category: str | None = None, language: str | None = None
) -> list[WarmupBootstrapChannel]:
    return repository.list_channels(session, category=category, language=language)


def create_bootstrap_channel(
    session: Session,
    *,
    channel_ref: str,
    category: str,
    language: str,
    country: str | None,
    added_by: str | None,
    verified_safe_at: datetime | None = None,
) -> WarmupBootstrapChannel:
    row, _created = repository.upsert_channel(
        session,
        channel_ref=channel_ref,
        category=category,
        language=language,
        country=country,
        added_by=added_by,
        verified_safe_at=verified_safe_at,
    )
    session.commit()
    return row


def patch_bootstrap_channel(
    session: Session,
    channel_id: str,
    *,
    category: str | None = None,
    language: str | None = None,
    country: str | None = None,
    is_active: bool | None = None,
) -> WarmupBootstrapChannel | None:
    row = repository.patch_channel(
        session,
        channel_id,
        category=category,
        language=language,
        country=country,
        is_active=is_active,
    )
    if row is not None:
        session.commit()
    return row


def resolve_available_targets(
    session: Session,
    *,
    warmup_session: WarmupSession,
    rng: random.Random,
    count: int = 8,
) -> list[str]:
    strategy_targets = _target_channel_refs(warmup_session)
    if strategy_targets:
        return strategy_targets
    return repository.get_random_channels(
        session,
        language=_session_language(warmup_session),
        country=_session_country(warmup_session),
        count=count,
        exclude=[],
        rng=rng,
    )


def run_bootstrap_channel_health_check(session: Session) -> int:
    processed = 0
    for row in repository.list_channels(session, active_only=True):
        processed += 1
        if not _is_locally_safe(row):
            row.is_active = False
            row.updated_at = utc_now()
    session.flush()
    return processed


def _is_locally_safe(row: WarmupBootstrapChannel) -> bool:
    try:
        repository.normalize_channel_ref(row.channel_ref)
        repository.normalize_category(row.category)
        repository.normalize_language(row.language)
    except ValueError:
        return False
    return row.verified_safe_at is not None


def _session_language(warmup_session: WarmupSession) -> str:
    raw = (warmup_session.strategy_snapshot_json or {}).get("bootstrap_language")
    return raw if isinstance(raw, str) and raw.strip() else "en"


def _session_country(warmup_session: WarmupSession) -> str | None:
    raw = (warmup_session.strategy_snapshot_json or {}).get("bootstrap_country")
    return raw if isinstance(raw, str) and raw.strip() else None
