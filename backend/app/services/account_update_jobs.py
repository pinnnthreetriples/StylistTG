"""Compatibility wrapper.

Canonical owner: app.modules.account_editing.service
Do not add new behavior here.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.models import Job
from app.modules.account_editing import service as account_editing_service
from app.modules.account_editing.errors import AccountEditingError
from app.services.execution_policy import ExecutionUsableAdapter


def build_account_update_preview(
    session: Session,
    *,
    account_id: str,
    desired_state: dict[str, Any],
    workspace_id: str | None = None,
    config: Settings = settings,
) -> dict[str, Any]:
    try:
        return account_editing_service.build_account_update_preview(
            session,
            account_id=account_id,
            desired_state=desired_state,
            workspace_id=workspace_id,
            config=config,
        )
    except AccountEditingError as exc:
        raise exc.to_value_error() from exc


def create_account_update_job(
    session: Session,
    *,
    account_id: str,
    desired_state: dict[str, Any],
    execution_adapter: ExecutionUsableAdapter | None = None,
    config: Settings = settings,
    requested_by_user_id: str | None = None,
    created_from: str = "api",
    request_id: str | None = None,
    workspace_id: str | None = None,
) -> Job:
    try:
        return account_editing_service.create_account_update_job(
            session,
            account_id=account_id,
            desired_state=desired_state,
            execution_adapter=execution_adapter,
            config=config,
            requested_by_user_id=requested_by_user_id,
            created_from=created_from,
            request_id=request_id,
            workspace_id=workspace_id,
        )
    except AccountEditingError as exc:
        raise exc.to_value_error() from exc


__all__ = [
    "build_account_update_preview",
    "create_account_update_job",
    "settings",
]
