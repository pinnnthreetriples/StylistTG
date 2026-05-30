from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

BoughtOnboardingStep = Literal[
    "enable_2fa",
    "terminate_other_sessions",
    "rest_period",
    "ggr_precheck",
    "completed",
]


def _serialize_utc_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat().replace("+00:00", "Z")


class BoughtOnboardingStatusRead(BaseModel):
    account_id: str
    current_step: BoughtOnboardingStep
    completion_percent: int = Field(ge=0, le=100)
    started_at: datetime
    completed_at: datetime | None = None
    details_json: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("started_at", "completed_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        return _serialize_utc_datetime(value)


__all__ = ["BoughtOnboardingStatusRead", "BoughtOnboardingStep"]
