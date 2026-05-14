"""RQ entrypoint for warmup dispatch tick (Phase 1 shadow execution)."""

from __future__ import annotations

from app.modules.warmup import jobs


def run_warmup_dispatch_tick() -> int:
    return jobs.run_warmup_dispatch_tick()
