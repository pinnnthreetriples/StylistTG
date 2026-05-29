from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

AccountStatusAutoAction = Literal["paused", "quarantine", "cooldown", "none"]


def _serialize_utc_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat().replace("+00:00", "Z")


class AccountStatusObservationRead(BaseModel):
    id: str
    workspace_id: str
    account_id: str
    observed_at: datetime
    proxy_healthy: bool
    proxy_ip_hash: str | None = None
    tdlib_authorized: bool
    device_model_hash: str | None = None
    consecutive_failures: int = Field(ge=0)
    auto_action_taken: AccountStatusAutoAction | None = None
    details_json: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("observed_at")
    def _serialize_datetime(self, value: datetime) -> str:
        return _serialize_utc_datetime(value)


__all__ = ["AccountStatusAutoAction", "AccountStatusObservationRead"]
