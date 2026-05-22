from __future__ import annotations

from datetime import UTC, datetime

from app.contracts.types import UuidString
from pydantic import BaseModel, ConfigDict, Field, field_serializer


def _serialize_utc_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class DisasterState(BaseModel):
    workspace_id: UuidString
    is_disaster: bool
    quarantined_count: int
    total_accounts: int
    quarantined_fraction: float = Field(ge=0.0, le=1.0)
    threshold: float = 0.5
    window_hours: int = 1
    detected_at: datetime
    sample_quarantined_account_ids: list[UuidString]

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("detected_at")
    def _serialize_datetime(self, value: datetime) -> str:
        return _serialize_utc_datetime(value)
