from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer


def _serialize_utc_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat().replace("+00:00", "Z")


class ProfileCompletenessReport(BaseModel):
    account_id: UUID
    score: float = Field(ge=0.0, le=1.0)
    breakdown: dict[str, bool]
    missing_required: list[str]
    missing_recommended: list[str]
    evaluated_at: datetime

    @field_serializer("evaluated_at")
    def _serialize_datetime(self, value: datetime) -> str:
        return _serialize_utc_datetime(value)


__all__ = ["ProfileCompletenessReport"]
