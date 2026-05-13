from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.adapters.tdlib_profile_execution import build_profile_execution_adapter
from app.config import Settings, settings
from app.job_queue.workflows import enqueue_workflow
from app.models import Job
from app.services.account_update_jobs import (
    build_account_update_preview,
    create_account_update_job,
)
from app.workers.account_update_jobs import execute_account_update_job


ACCOUNT_UPDATE_WORKFLOW_TYPE = "account_update"


def build_preview(
    session: Session,
    *,
    account_id: str,
    desired_state: dict[str, Any],
    workspace_id: str,
    config: Settings = settings,
) -> dict[str, Any]:
    return build_account_update_preview(
        session,
        account_id=account_id,
        desired_state=desired_state,
        workspace_id=workspace_id,
        config=config,
    )


def create_job(
    session: Session,
    *,
    account_id: str,
    desired_state: dict[str, Any],
    requested_by_user_id: str | None,
    request_id: str | None,
    workspace_id: str,
    config: Settings = settings,
) -> Job:
    return create_account_update_job(
        session,
        account_id=account_id,
        desired_state=desired_state,
        execution_adapter=build_profile_execution_adapter(),
        config=config,
        requested_by_user_id=requested_by_user_id,
        request_id=request_id,
        workspace_id=workspace_id,
    )


def enqueue_job(job_id: str) -> bool:
    return enqueue_workflow(
        workflow_type=ACCOUNT_UPDATE_WORKFLOW_TYPE,
        job_id=job_id,
    )


def execute_inline_fallback(job_id: str, *, session: Session) -> None:
    execute_account_update_job(job_id, session=session)
