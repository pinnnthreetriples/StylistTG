from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class JobSummaryRead(BaseModel):
    job_id: str
    job_state: str
    execution_intent_hash: str
    plan_summary: list[str]
    created_at: datetime | None
    dedup_blocked_by_job_id: str | None = None
    message: str | None = None


__all__ = ["JobSummaryRead"]
