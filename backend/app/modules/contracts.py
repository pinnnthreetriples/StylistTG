from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class WorkflowArgsMode(StrEnum):
    JOB_ID = "job_id"
    NONE = "none"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class WorkflowSpec:
    workflow_type: str
    queue_name: str
    handler_path: str
    args_mode: WorkflowArgsMode
    description: str


@dataclass(frozen=True, slots=True)
class FeatureModule:
    name: str
    workflows: tuple[WorkflowSpec, ...]
