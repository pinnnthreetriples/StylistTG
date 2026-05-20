from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base
from app.models import UUIDString, new_id, utc_now

QUARANTINE_REASONS = (
    "flood_wait",
    "status_degraded",
    "manual",
    "bought_rest_period",
    "fraud_high",
)


class AccountQuarantine(Base):
    __tablename__ = "account_quarantines"
    __table_args__ = (
        CheckConstraint(
            "reason IN ('flood_wait', 'status_degraded', 'manual', 'bought_rest_period', 'fraud_high')",
            name="ck_account_quarantines_reason",
        ),
        Index("ix_account_quarantines_ws_account_until", "workspace_id", "account_id", "until"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account.id"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_by_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


__all__ = ["AccountQuarantine", "QUARANTINE_REASONS"]
