from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_serializer

QuarantineReason = Literal[
    "flood_wait",
    "status_degraded",
    "manual",
    "bought_rest_period",
    "fraud_high",
]


def _serialize_utc_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat().replace("+00:00", "Z")


class AccountQuarantineRead(BaseModel):
    id: str
    workspace_id: str
    account_id: str
    reason: QuarantineReason
    started_at: datetime
    until: datetime
    released_at: datetime | None = None
    released_by_user_id: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("started_at", "until", "released_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        return _serialize_utc_datetime(value)


class ReleaseRequest(BaseModel):
    reason: Annotated[str | None, Field(default=None, max_length=1000)] = None
    override_gate_block: StrictBool = False

    model_config = ConfigDict(extra="forbid")


__all__ = ["AccountQuarantineRead", "QuarantineReason", "ReleaseRequest"]
