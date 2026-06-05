from __future__ import annotations

# ruff: noqa: F403,F405
# jscpd:ignore-start

from app.models import *


class WarmupBootstrapChannel(Base):
    __tablename__ = "warmup_bootstrap_channel"
    __table_args__ = (
        UniqueConstraint("channel_ref", name="uq_warmup_bootstrap_channel_ref"),
        Index("ix_warmup_bootstrap_channel_category", "category"),
        Index("ix_warmup_bootstrap_channel_language_country", "language", "country"),
        Index("ix_warmup_bootstrap_channel_is_active", "is_active"),
        CheckConstraint("channel_ref LIKE '@%'", name="ck_warmup_bootstrap_channel_ref_public"),
        CheckConstraint(
            "category IN ('news','tech','lifestyle','sports','entertainment','business')",
            name="ck_warmup_bootstrap_channel_category",
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    channel_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    verified_safe_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    added_by: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


# jscpd:ignore-end
