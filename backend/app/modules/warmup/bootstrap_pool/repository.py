from __future__ import annotations

import random
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WarmupBootstrapChannel, new_id, utc_now

BOOTSTRAP_CATEGORIES = frozenset(
    {"news", "tech", "lifestyle", "sports", "entertainment", "business"}
)


def list_channels(
    session: Session,
    *,
    category: str | None = None,
    language: str | None = None,
    active_only: bool = False,
) -> list[WarmupBootstrapChannel]:
    query = select(WarmupBootstrapChannel).order_by(WarmupBootstrapChannel.channel_ref)
    if category:
        query = query.where(WarmupBootstrapChannel.category == category)
    if language:
        query = query.where(WarmupBootstrapChannel.language == language)
    if active_only:
        query = query.where(WarmupBootstrapChannel.is_active.is_(True))
    return list(session.execute(query).scalars())


def get_random_channels(
    session: Session,
    language: str | None,
    country: str | None,
    count: int,
    exclude: Iterable[str] | None = None,
    *,
    rng: random.Random | None = None,
) -> list[str]:
    excluded = set(exclude or ())
    candidates = _candidate_refs(session, language=language, country=country, exclude=excluded)
    if not candidates:
        return []
    sampler = rng or random.Random()
    if len(candidates) <= count:
        sampler.shuffle(candidates)
        return candidates
    return sampler.sample(candidates, count)


def upsert_channel(
    session: Session,
    *,
    channel_ref: str,
    category: str,
    language: str,
    country: str | None,
    verified_safe_at: datetime | None = None,
    added_by: str | None = None,
    is_active: bool = True,
) -> tuple[WarmupBootstrapChannel, bool]:
    existing = (
        session.execute(
            select(WarmupBootstrapChannel).where(
                WarmupBootstrapChannel.channel_ref == normalize_channel_ref(channel_ref)
            )
        )
        .scalars()
        .first()
    )
    if existing is None:
        row = WarmupBootstrapChannel(
            id=new_id(),
            channel_ref=normalize_channel_ref(channel_ref),
            category=normalize_category(category),
            language=normalize_language(language),
            country=normalize_country(country),
            verified_safe_at=verified_safe_at or utc_now(),
            added_by=added_by,
            is_active=is_active,
        )
        session.add(row)
        session.flush()
        return row, True
    existing.category = normalize_category(category)
    existing.language = normalize_language(language)
    existing.country = normalize_country(country)
    existing.verified_safe_at = verified_safe_at or existing.verified_safe_at
    existing.added_by = added_by or existing.added_by
    existing.is_active = is_active
    existing.updated_at = utc_now()
    session.flush()
    return existing, False


def patch_channel(
    session: Session,
    channel_id: str,
    *,
    category: str | None = None,
    language: str | None = None,
    country: str | None = None,
    is_active: bool | None = None,
) -> WarmupBootstrapChannel | None:
    row = session.get(WarmupBootstrapChannel, channel_id)
    if row is None:
        return None
    if category is not None:
        row.category = normalize_category(category)
    if language is not None:
        row.language = normalize_language(language)
    if country is not None:
        row.country = normalize_country(country)
    if is_active is not None:
        row.is_active = is_active
    row.updated_at = utc_now()
    session.flush()
    return row


def normalize_channel_ref(value: str) -> str:
    ref = value.strip()
    if not ref.startswith("@") or len(ref) < 2:
        raise ValueError("channel_ref must be a public @username")
    if "/" in ref or " " in ref:
        raise ValueError("channel_ref must not contain spaces or invite links")
    return ref


def normalize_category(value: str) -> str:
    category = value.strip().lower()
    if category not in BOOTSTRAP_CATEGORIES:
        raise ValueError("unsupported bootstrap channel category")
    return category


def normalize_language(value: str) -> str:
    language = value.strip().lower()
    if not language:
        raise ValueError("language is required")
    return language


def normalize_country(value: str | None) -> str | None:
    if value is None:
        return None
    country = value.strip().upper()
    return country or None


def _candidate_refs(
    session: Session,
    *,
    language: str | None,
    country: str | None,
    exclude: set[str],
) -> list[str]:
    rows = list_channels(session, active_only=True)
    language = normalize_language(language or "en")
    country = normalize_country(country)
    tiers = [
        [
            row.channel_ref
            for row in rows
            if row.language == language
            and (country is None or row.country == country)
            and row.channel_ref not in exclude
        ],
        [
            row.channel_ref
            for row in rows
            if row.language == language and row.channel_ref not in exclude
        ],
        [row.channel_ref for row in rows if row.language == "en" and row.channel_ref not in exclude],
        [row.channel_ref for row in rows if row.channel_ref not in exclude],
    ]
    for refs in tiers:
        unique = list(dict.fromkeys(refs))
        if unique:
            return unique
    return []
