from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


CrossModuleName = Literal["warmup", "commenting", "editing", "other"]
CrossModuleLoadBreakdown = dict[CrossModuleName, int]


class CrossModuleLoad(BaseModel):
    last_hour: int = Field(ge=0)
    last_24h: int = Field(ge=0)
    breakdown: CrossModuleLoadBreakdown

    model_config = ConfigDict(frozen=True)


__all__ = [
    "CrossModuleLoad",
    "CrossModuleLoadBreakdown",
    "CrossModuleName",
    "ProfileAudioAction",
    "ProfilePreviewRead",
    "ProfilePreviewStepRead",
]
