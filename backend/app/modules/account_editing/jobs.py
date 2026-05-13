from __future__ import annotations

from app.modules.account_editing.executor import execute_account_update_job


def run_account_update_job(job_id: str) -> None:
    execute_account_update_job(job_id)
