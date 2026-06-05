from __future__ import annotations

# ruff: noqa: F403,F405
# jscpd:ignore-start

from app.models import *


class WarmupChannelState(Base):
    __tablename__ = "warmup_channel_state"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "account_id",
            "channel_ref",
            name="ix_warmup_channel_state_workspace_account_channel",
        ),
        Index("ix_warmup_channel_state_workspace_id", "workspace_id"),
        CheckConstraint(
            "health_score >= 0.0 AND health_score <= 1.0",
            name="ck_warmup_channel_state_health_score",
        ),
        CheckConstraint("success_count >= 0", name="ck_warmup_channel_state_success_count"),
        CheckConstraint("fail_count >= 0", name="ck_warmup_channel_state_fail_count"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False)
    channel_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    subscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_feed_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_story_view_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_react_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_browse_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    has_stories: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_reactions: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    available_reactions_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    health_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


# jscpd:ignore-end
