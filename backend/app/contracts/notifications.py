from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

TriggerCode = Literal[
    "quarantine_epidemic",
    "ggr_drop",
    "gate_block_burst",
    "proxy_outage",
]


class NotificationPayload(BaseModel):
    workspace_id: UUID
    trigger_code: TriggerCode
    severity: Literal["warning", "critical"]
    title: str
    body_text: str
    metadata: dict[str, Any]
    triggered_at: datetime


class NotificationDeliveryResult(BaseModel):
    channel: Literal["email", "webhook"]
    success: bool
    error: str | None = None
    attempted_at: datetime
