from __future__ import annotations

import os
import socket

from app.db import SessionLocal
from app.services.warmup_worker import process_due_warmup_sessions


def run_warmup_due_sessions() -> int:
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    with SessionLocal() as session:
        return process_due_warmup_sessions(session, worker_id=worker_id)
