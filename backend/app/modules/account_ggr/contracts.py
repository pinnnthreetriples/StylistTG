from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


GgrBucket = Literal["strong", "medium", "weak"]


def _serialize_utc_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat().replace("+00:00", "Z")


class GgrBreakdownRead(BaseModel):
    age: float = Field(ge=0.0, le=1.0)
    origin: float = Field(ge=0.0, le=1.0)
    history: float = Field(ge=0.0, le=1.0)
    proxy: float = Field(ge=0.0, le=1.0)
    fingerprint: float = Field(ge=0.0, le=1.0)
    ip_change: float = Field(ge=0.0, le=1.0)
    session_anomaly: float = Field(ge=0.0, le=1.0)
    warmup: float = Field(ge=0.0, le=1.0)
    profile: float = Field(ge=0.0, le=1.0)


class GgrScoreRead(BaseModel):
    id: str
    account_id: str
    score: float = Field(ge=1.0, le=10.0)
    bucket: GgrBucket
    breakdown: GgrBreakdownRead
    previous_score: float | None = None
    last_calculated_at: datetime | None = None
    next_calculation_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("last_calculated_at", "next_calculation_at", "created_at", "updated_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return _serialize_utc_datetime(value)


__all__ = [
    "GgrBucket",
    "GgrBreakdownRead",
    "GgrScoreRead",
]
