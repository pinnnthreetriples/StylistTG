from __future__ import annotations

from app.workers.warmup_dispatch_jobs import run_warmup_dispatch_tick as _run_dispatch_tick
from app.workers.warmup_jobs import run_warmup_due_sessions as _run_due_sessions


def run_warmup_due_sessions() -> None:
    _run_due_sessions()


def run_warmup_dispatch_tick() -> None:
    _run_dispatch_tick()
