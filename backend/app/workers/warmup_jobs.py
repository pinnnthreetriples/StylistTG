from __future__ import annotations

from app.modules.warmup import jobs


def run_warmup_due_sessions() -> int:
    return jobs.run_warmup_due_sessions()
