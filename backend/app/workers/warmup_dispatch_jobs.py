"""RQ entrypoint for warmup dispatch tick (Phase 1 shadow execution)."""

from __future__ import annotations

import os
import socket

from app.db import SessionLocal
from app.services.warmup_dispatch import process_due_warmup_dispatches


def run_warmup_dispatch_tick() -> int:
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    with SessionLocal() as session:
        return process_due_warmup_dispatches(session, worker_id=worker_id)
