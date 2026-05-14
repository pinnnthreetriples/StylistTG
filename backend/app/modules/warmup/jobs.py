from __future__ import annotations

import os
import socket

from app.db import SessionLocal
from app.modules.warmup import dispatcher, worker


def run_warmup_due_sessions() -> int:
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    with SessionLocal() as session:
        return worker.process_due_warmup_sessions(session, worker_id=worker_id)


def run_warmup_dispatch_tick() -> int:
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    with SessionLocal() as session:
        return dispatcher.process_due_warmup_dispatches(session, worker_id=worker_id)
