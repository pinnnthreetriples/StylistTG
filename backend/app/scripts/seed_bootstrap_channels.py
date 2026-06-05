from __future__ import annotations

import argparse
from typing import Any

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.modules.warmup.bootstrap_pool.repository import upsert_channel

BOOTSTRAP_CHANNELS: list[dict[str, Any]] = [
    {"channel_ref": "@telegram", "category": "tech", "language": "en", "country": "US"},
    {"channel_ref": "@telegramtips", "category": "tech", "language": "en", "country": "US"},
    {"channel_ref": "@durov", "category": "tech", "language": "en", "country": "AE"},
    {"channel_ref": "@github", "category": "tech", "language": "en", "country": "US"},
    {"channel_ref": "@techcrunch", "category": "tech", "language": "en", "country": "US"},
    {"channel_ref": "@theverge", "category": "tech", "language": "en", "country": "US"},
    {"channel_ref": "@engadget", "category": "tech", "language": "en", "country": "US"},
    {"channel_ref": "@wired", "category": "tech", "language": "en", "country": "US"},
    {"channel_ref": "@habr_com", "category": "tech", "language": "ru", "country": "RU"},
    {"channel_ref": "@tproger_official", "category": "tech", "language": "ru", "country": "RU"},
    {"channel_ref": "@vcnews", "category": "tech", "language": "ru", "country": "RU"},
    {"channel_ref": "@dou_community", "category": "tech", "language": "ua", "country": "UA"},
    {"channel_ref": "@bbcnews", "category": "news", "language": "en", "country": "GB"},
    {"channel_ref": "@cnn", "category": "news", "language": "en", "country": "US"},
    {"channel_ref": "@nytimes", "category": "news", "language": "en", "country": "US"},
    {"channel_ref": "@euronews", "category": "news", "language": "en", "country": "EU"},
    {"channel_ref": "@dwnews", "category": "news", "language": "en", "country": "DE"},
    {"channel_ref": "@tass_agency", "category": "news", "language": "ru", "country": "RU"},
    {"channel_ref": "@rian_ru", "category": "news", "language": "ru", "country": "RU"},
    {"channel_ref": "@rbc_news", "category": "news", "language": "ru", "country": "RU"},
    {"channel_ref": "@kommersant", "category": "news", "language": "ru", "country": "RU"},
    {"channel_ref": "@vedomosti", "category": "news", "language": "ru", "country": "RU"},
    {"channel_ref": "@ukrpravda_news", "category": "news", "language": "ua", "country": "UA"},
    {"channel_ref": "@unian", "category": "news", "language": "ua", "country": "UA"},
    {"channel_ref": "@suspilnenews", "category": "news", "language": "ua", "country": "UA"},
    {"channel_ref": "@bloomberg", "category": "business", "language": "en", "country": "US"},
    {"channel_ref": "@businessinsider", "category": "business", "language": "en", "country": "US"},
    {"channel_ref": "@forbes", "category": "business", "language": "en", "country": "US"},
    {"channel_ref": "@wsj", "category": "business", "language": "en", "country": "US"},
    {"channel_ref": "@finamalert", "category": "business", "language": "ru", "country": "RU"},
    {"channel_ref": "@quote", "category": "business", "language": "ru", "country": "RU"},
    {"channel_ref": "@minfin", "category": "business", "language": "ua", "country": "UA"},
    {"channel_ref": "@espn", "category": "sports", "language": "en", "country": "US"},
    {"channel_ref": "@bleacherreport", "category": "sports", "language": "en", "country": "US"},
    {"channel_ref": "@skysports", "category": "sports", "language": "en", "country": "GB"},
    {"channel_ref": "@sportsru", "category": "sports", "language": "ru", "country": "RU"},
    {"channel_ref": "@championat", "category": "sports", "language": "ru", "country": "RU"},
    {"channel_ref": "@tribuna_ua", "category": "sports", "language": "ua", "country": "UA"},
    {"channel_ref": "@natgeo", "category": "lifestyle", "language": "en", "country": "US"},
    {"channel_ref": "@nasa", "category": "lifestyle", "language": "en", "country": "US"},
    {"channel_ref": "@ted", "category": "lifestyle", "language": "en", "country": "US"},
    {"channel_ref": "@lifehacker", "category": "lifestyle", "language": "en", "country": "US"},
    {"channel_ref": "@lifehacker_ru", "category": "lifestyle", "language": "ru", "country": "RU"},
    {"channel_ref": "@afishadaily", "category": "lifestyle", "language": "ru", "country": "RU"},
    {"channel_ref": "@platfor_ma", "category": "lifestyle", "language": "ua", "country": "UA"},
    {"channel_ref": "@netflix", "category": "entertainment", "language": "en", "country": "US"},
    {"channel_ref": "@youtube", "category": "entertainment", "language": "en", "country": "US"},
    {"channel_ref": "@spotify", "category": "entertainment", "language": "en", "country": "SE"},
    {"channel_ref": "@kinopoisk", "category": "entertainment", "language": "ru", "country": "RU"},
    {"channel_ref": "@bookmate_ru", "category": "entertainment", "language": "ru", "country": "RU"},
    {"channel_ref": "@megogo_ua", "category": "entertainment", "language": "ua", "country": "UA"},
    {"channel_ref": "@hromadske_ua", "category": "news", "language": "ua", "country": "UA"},
]


def seed_bootstrap_channels(session: Session) -> int:
    created = 0
    for item in BOOTSTRAP_CHANNELS:
        _row, was_created = upsert_channel(session, **item)
        created += int(was_created)
    session.commit()
    return created


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(f"seed_count={len(BOOTSTRAP_CHANNELS)}")
        return
    with SessionLocal() as session:
        created = seed_bootstrap_channels(session)
    print(f"created={created}")


if __name__ == "__main__":
    main()
