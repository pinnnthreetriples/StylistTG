from __future__ import annotations

# ruff: noqa: F403,F405
# jscpd:ignore-start

from app.models import *


class AccountSurvivalMetric(Base):
    __tablename__ = "account_survival_metric"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "account_id",
            name="uq_account_survival_metric_workspace_account",
        ),
        Index("ix_account_survival_metric_workspace_id", "workspace_id"),
        Index("ix_account_survival_metric_account_id", "account_id"),
        Index(
            "ix_account_survival_metric_banned_at",
            "banned_at",
            postgresql_where=text("banned_at IS NOT NULL"),
            sqlite_where=text("banned_at IS NOT NULL"),
        ),
        CheckConstraint("freeze_count >= 0", name="ck_account_survival_freeze_count"),
        CheckConstraint("flood_wait_count >= 0", name="ck_account_survival_flood_wait_count"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account.id", ondelete="CASCADE"), nullable=False
    )
    warmup_strategy_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    warmup_strategy_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    warmup_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    warmup_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pre_production_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_action_after_warmup_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_freeze_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_unfreeze_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    freeze_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    flood_wait_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    survival_days: Mapped[int | None] = mapped_column(
        Integer,
        Computed(
            "CAST(julianday(COALESCE(banned_at, deleted_at, updated_at)) - "
            "julianday(imported_at) AS INTEGER)"
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


# jscpd:ignore-end
