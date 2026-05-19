from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer


def _serialize_utc_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat().replace("+00:00", "Z")


class BehaviorProfileRead(BaseModel):
    id: str
    account_id: str
    workspace_id: str
    typing_speed_baseline_cpm: int
    typo_rate_baseline: float = Field(ge=0.0, le=1.0)
    profile_view_probability_baseline: float = Field(ge=0.0, le=1.0)
    scroll_probability_baseline: float = Field(ge=0.0, le=1.0)
    message_deletion_probability_baseline: float = Field(ge=0.0, le=1.0)
    action_sequence_seed: int
    last_randomization_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("last_randomization_at", "created_at", "updated_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return _serialize_utc_datetime(value)


__all__ = [
    "BehaviorProfileRead",
]
