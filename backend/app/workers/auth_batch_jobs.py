from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.db import SessionLocal
from app.services.auth_batch_tdlib import run_batch_start_auth as run_batch_start_auth_service


def run_batch_start_auth(
    item_id: str, *, session_factory: sessionmaker[Session] | None = None
) -> None:
    factory = session_factory or SessionLocal
    with factory() as session:
        item = run_batch_start_auth_service(session, item_id)
        if item.batch.status == "running":
            from app.services.auth_batch_dispatcher import dispatch_once

            dispatch_once(session, item.batch_id)
