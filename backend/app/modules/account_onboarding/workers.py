from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.db import SessionLocal
from app.modules.account_onboarding.service import execute_item, expire_artifacts


def run_onboarding_item(
    item_id: str, *, session_factory: sessionmaker[Session] | None = None
) -> None:
    factory = session_factory or SessionLocal
    with factory() as session:
        execute_item(session, item_id=item_id)


def expire_onboarding_artifacts(*, session_factory: sessionmaker[Session] | None = None) -> int:
    factory = session_factory or SessionLocal
    with factory() as session:
        return expire_artifacts(session)


__all__ = ["expire_onboarding_artifacts", "run_onboarding_item"]
