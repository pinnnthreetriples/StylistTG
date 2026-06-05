from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AccountDeletionPlannedActionRead(BaseModel):
    type: str
    resource: str
    count: int | None = None
    present: bool | None = None
    retention_policy: str | None = None


class AccountDeletionPreviewRead(BaseModel):
    account_id: str
    can_delete: bool
    risk_level: str
    risk_score: int
    blocking_reasons: list[str]
    planned_actions: list[AccountDeletionPlannedActionRead]
    requires_confirmation: bool
    generated_at: datetime


class AccountDeletionRequestCreate(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)
    confirmation: Literal["DELETE"]
    dry_run: bool = True


class AccountDeletionRequestRead(BaseModel):
    id: str
    account_id: str
    status: str
    reason: str | None = None
    dry_run_result: dict[str, Any] | None = None
    execution_result: dict[str, Any] | None = None
    requested_at: datetime
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    failure_code: str | None = None
    failure_message: str | None = None


class AccountExportRequestRead(BaseModel):
    id: str
    account_id: str
    status: str
    export_key: str | None = None
    export_size_bytes: int | None = None
    export_content_type: str | None = None
    requested_at: datetime
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    expires_at: datetime | None = None


class AccountLifecycleEventRead(BaseModel):
    id: str
    from_state: str | None = None
    to_state: str | None = None
    reason: str | None = None
    actor_user_id: str | None = None
    occurred_at: datetime
    payload: dict[str, Any]


class AccountLifecycleRead(BaseModel):
    account_id: str
    lifecycle_state: str
    lifecycle_updated_at: datetime | None = None
    history: list[AccountLifecycleEventRead]
