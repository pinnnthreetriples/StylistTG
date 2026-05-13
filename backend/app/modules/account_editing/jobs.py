from __future__ import annotations

from app.workers.account_update_jobs import execute_account_update_job


def run_account_update_job(job_id: str) -> None:
    execute_account_update_job(job_id)
