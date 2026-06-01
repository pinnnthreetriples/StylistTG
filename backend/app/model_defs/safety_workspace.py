from __future__ import annotations

# pyright: reportConstantRedefinition=false

# ruff: noqa: F403,F405
# jscpd:ignore-start

from app.models import *


class AccountQuarantine(Base):
    __tablename__ = "account_quarantines"
    __table_args__ = (
        CheckConstraint(
            "reason IN ('flood_wait', 'status_degraded', 'manual', 'bought_rest_period', 'fraud_high')",
            name="ck_account_quarantines_reason",
        ),
        Index(
            "ix_account_quarantines_ws_account_until",
            "workspace_id",
            "account_id",
            "until",
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_by_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


ACCOUNT_STATUS_AUTO_ACTIONS = ("paused", "quarantine", "cooldown", "none")


class AccountStatusObservation(Base):
    __tablename__ = "account_status_observations"
    __table_args__ = (
        CheckConstraint(
            "auto_action_taken IS NULL OR auto_action_taken IN ('paused', 'quarantine', 'cooldown', 'none')",
            name="ck_account_status_observations_auto_action",
        ),
        Index(
            "ix_account_status_observations_account_observed",
            "account_id",
            "observed_at",
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    proxy_healthy: Mapped[bool] = mapped_column(Boolean, nullable=False)
    proxy_ip_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    tdlib_authorized: Mapped[bool] = mapped_column(Boolean, nullable=False)
    device_model_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    auto_action_taken: Mapped[str | None] = mapped_column(String(32), nullable=True)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class CrossModuleLoadBucket(Base):
    __tablename__ = "cross_module_load_buckets"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "account_id",
            "bucket_start",
            name="uq_cross_module_load_buckets_ws_account_bucket",
        ),
        Index("ix_cross_module_load_buckets_bucket_start", "bucket_start"),
        Index(
            "ix_cross_module_load_buckets_account_bucket_start",
            "account_id",
            "bucket_start",
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    warmup_actions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    commenting_actions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    editing_actions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    other_actions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_actions: Mapped[int] = mapped_column(
        Integer,
        Computed(
            "warmup_actions + commenting_actions + editing_actions + other_actions",
            persisted=True,
        ),
        nullable=False,
    )


class AccountGgrScore(Base):
    __tablename__ = "account_ggr_scores"
    __table_args__ = (
        UniqueConstraint("workspace_id", "account_id", name="uq_account_ggr_scores_ws_account"),
        CheckConstraint("score >= 1.0 AND score <= 10.0", name="ck_account_ggr_scores_range"),
        CheckConstraint(
            "bucket IN ('strong', 'medium', 'weak')",
            name="ck_account_ggr_scores_bucket",
        ),
        Index("ix_account_ggr_scores_workspace_id", "workspace_id"),
        Index("ix_account_ggr_scores_account_id", "account_id"),
        Index("ix_account_ggr_scores_next_calculation", "next_calculation_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    bucket: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    breakdown_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    previous_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    next_calculation_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_calculated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AccountBehaviorProfile(Base):
    __tablename__ = "account_behavior_profile"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "account_id", name="uq_account_behavior_profile_ws_account"
        ),
        Index("ix_account_behavior_profile_workspace_id", "workspace_id"),
        Index("ix_account_behavior_profile_account_id", "account_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
    )
    typing_speed_baseline_cpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    typo_rate_baseline: Mapped[float] = mapped_column(Float, nullable=False)
    profile_view_probability_baseline: Mapped[float] = mapped_column(Float, nullable=False)
    scroll_probability_baseline: Mapped[float] = mapped_column(Float, nullable=False)
    message_deletion_probability_baseline: Mapped[float] = mapped_column(Float, nullable=False)
    action_sequence_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    last_randomization_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class WorkspacePlan(Base):
    __tablename__ = "workspace_plan"

    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), primary_key=True
    )
    plan_code: Mapped[str] = mapped_column(String(64), nullable=False, default="local")
    billing_status: Mapped[str] = mapped_column(String(64), nullable=False, default="active")
    max_accounts: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    max_jobs_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)
    max_batch_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    max_storage_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=10240)
    max_team_members: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class RuntimeSetting(Base):
    __tablename__ = "runtime_setting"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class UsageCounter(Base):
    __tablename__ = "usage_counter"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "period_start",
            "period_end",
            "metric",
            name="uq_usage_counter_period_metric",
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metric: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# jscpd:ignore-end
