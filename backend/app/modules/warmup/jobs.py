from __future__ import annotations

import os
import socket
from datetime import UTC, datetime

from app.db import SessionLocal
from app.modules.warmup import dispatcher, worker
from app.modules.warmup.bootstrap_pool.service import run_bootstrap_channel_health_check
from app.modules.warmup.idle_session import run_idle_warmup_sweep_all_workspaces
from app.modules.warmup.pre_production import complete_due_pre_production_sessions


def run_warmup_due_sessions() -> int:
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    with SessionLocal() as session:
        return worker.process_due_warmup_sessions(session, worker_id=worker_id)


def run_warmup_dispatch_tick() -> int:
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    with SessionLocal() as session:
        if dispatcher.dispatch_stagger_enabled():
            return int(dispatcher.enqueue_due_warmup_dispatch_sessions(session))
        return dispatcher.process_due_warmup_dispatches(session, worker_id=worker_id)


def run_warmup_dispatch_session(
    session_id: str,
    scheduled_at: str | None = None,
    *,
    now: datetime | None = None,
) -> int:
    timestamp = now or datetime.now(UTC)
    scheduled_for = _parse_scheduled_at(scheduled_at)
    if scheduled_for is not None and timestamp < scheduled_for:
        return 0
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    with SessionLocal() as session:
        return dispatcher.process_warmup_dispatch_session(
            session,
            session_id=session_id,
            worker_id=worker_id,
            now=timestamp,
        )


def run_warmup_idle_sweep() -> int:
    with SessionLocal() as session:
        processed = run_idle_warmup_sweep_all_workspaces(session)
        session.commit()
        return processed


def run_warmup_pre_production_sweep() -> int:
    with SessionLocal() as session:
        processed = complete_due_pre_production_sessions(session)
        session.commit()
        return processed


def run_warmup_bootstrap_channel_health_check() -> int:
    with SessionLocal() as session:
        processed = run_bootstrap_channel_health_check(session)
        session.commit()
        return processed


def _parse_scheduled_at(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
