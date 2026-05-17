from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class ProfileAudioAction(StrEnum):
    KEEP = "keep"
    ADD = "add"
    REMOVE = "remove"


class ProfilePreviewStepRead(BaseModel):
    step_key: str
    step_type: str
    order: int
    required: bool
    idempotency_class: str
    payload: dict[str, Any]


class ProfilePreviewRead(BaseModel):
    can_create_job: bool
    blocking_errors: list[str]
    warnings: list[str]
    normalized_payload: dict[str, Any]
    execution_intent_hash: str
    plan_json_snapshot: dict[str, Any]
    steps: list[ProfilePreviewStepRead]
    requires_execution_usable: bool
    dedup_would_block: bool
    dedup_blocked_by_job_id: str | None


__all__ = ["ProfileAudioAction", "ProfilePreviewRead", "ProfilePreviewStepRead"]
