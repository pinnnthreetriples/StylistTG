"""Compatibility wrapper.

Canonical owner: app.modules.warmup.jobs
Do not add new behavior here.
"""

from __future__ import annotations

from app.modules.warmup import jobs


def run_warmup_dispatch_tick() -> int:
    return jobs.run_warmup_dispatch_tick()
