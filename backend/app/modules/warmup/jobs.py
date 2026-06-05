from __future__ import annotations

import os
import socket

from app.db import SessionLocal
from app.modules.warmup import dispatcher, worker
from app.modules.warmup.idle_session import run_idle_warmup_sweep_all_workspaces
from app.modules.warmup.pre_production import complete_due_pre_production_sessions


def run_warmup_due_sessions() -> int:
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    with SessionLocal() as session:
        return worker.process_due_warmup_sessions(session, worker_id=worker_id)


def run_warmup_dispatch_tick() -> int:
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    with SessionLocal() as session:
        return dispatcher.process_due_warmup_dispatches(session, worker_id=worker_id)


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
