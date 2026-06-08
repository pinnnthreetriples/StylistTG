from __future__ import annotations

import random

from sqlalchemy import select

from app.models import WarmupBootstrapChannel, new_id
from app.modules.warmup.bootstrap_pool.repository import get_random_channels, upsert_channel
from app.modules.warmup.bootstrap_pool.service import run_bootstrap_channel_health_check
from app.scripts.seed_bootstrap_channels import BOOTSTRAP_CHANNELS, seed_bootstrap_channels


def test_seed_bootstrap_channels_creates_minimum_safe_pool_idempotently(db_session) -> None:
    assert len(BOOTSTRAP_CHANNELS) >= 50

    created = seed_bootstrap_channels(db_session)
    second = seed_bootstrap_channels(db_session)

    rows = db_session.execute(select(WarmupBootstrapChannel)).scalars().all()
    assert created == len(BOOTSTRAP_CHANNELS)
    assert second == 0
    assert len(rows) >= 50
    assert {row.category for row in rows} >= {
        "news",
        "tech",
        "lifestyle",
        "sports",
        "entertainment",
        "business",
    }
    assert all(row.channel_ref.startswith("@") for row in rows)


def test_get_random_channels_prefers_language_country_and_excludes_refs(db_session) -> None:
    random.seed(0)
    upsert_channel(
        db_session,
        channel_ref="@bootstrap_en_us",
        category="tech",
        language="en",
        country="US",
    )
    upsert_channel(
        db_session,
        channel_ref="@bootstrap_en_gb",
        category="news",
        language="en",
        country="GB",
    )
    upsert_channel(
        db_session,
        channel_ref="@bootstrap_ru",
        category="news",
        language="ru",
        country="RU",
    )
    db_session.commit()

    refs = get_random_channels(
        db_session,
        language="en",
        country="US",
        count=3,
        exclude={"@bootstrap_en_us"},
        rng=random.Random(0),
    )

    assert "@bootstrap_en_us" not in refs
    assert refs == ["@bootstrap_en_gb"]


def test_health_check_disables_locally_invalid_active_refs(db_session) -> None:
    valid, _created = upsert_channel(
        db_session,
        channel_ref="@bootstrap_valid",
        category="tech",
        language="en",
        country="US",
    )
    invalid = WarmupBootstrapChannel(
        id=new_id(),
        channel_ref="@bad/link",
        category="news",
        language="en",
        country="US",
        is_active=True,
    )
    db_session.add(invalid)
    db_session.commit()

    processed = run_bootstrap_channel_health_check(db_session)
    db_session.commit()

    db_session.refresh(valid)
    db_session.refresh(invalid)
    assert processed == 2
    assert valid.is_active is True
    assert invalid.is_active is False
