from __future__ import annotations

# ruff: noqa: F403,F405
# jscpd:ignore-start

from app.models import *


class WarmupStrategy(Base):
    __tablename__ = "warmup_strategy"
    __table_args__ = (
        CheckConstraint(
            "execution_mode IN ('dry_run', 'shadow', 'passive', 'network', 'advanced')",
            name="ck_warmup_strategy_execution_mode",
        ),
        CheckConstraint(
            "preset_kind IN ('express', 'standard', 'hardened', 'custom')",
            name="ck_warmup_strategy_preset_kind",
        ),
        CheckConstraint("duration_days BETWEEN 3 AND 30", name="ck_warmup_strategy_duration_days"),
        UniqueConstraint("workspace_id", "name", name="uq_warmup_strategy_workspace_name"),
        Index("ix_warmup_strategy_workspace_id", "workspace_id"),
        Index("ix_warmup_strategy_preset", "is_preset"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tier_limits_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    target_channels_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    is_preset: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    execution_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default=WarmupExecutionMode.DRY_RUN
    )
    preset_kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default=WarmupPresetKind.CUSTOM
    )
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    daily_action_limits_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    session_window_config_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    ui_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    sessions: Mapped[list[WarmupSession]] = relationship(back_populates="strategy")


class WarmupSession(Base):
    __tablename__ = "warmup_session"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'validating', 'scheduled', 'cold_soak', 'active', 'paused_risk', 'paused_manual', 'completed', 'failed')",
            name="ck_warmup_session_status",
        ),
        CheckConstraint("current_day BETWEEN 0 AND 30", name="ck_warmup_session_current_day"),
        CheckConstraint("duration_days BETWEEN 3 AND 30", name="ck_warmup_session_duration_days"),
        CheckConstraint("cadence_hours >= 1", name="ck_warmup_session_cadence_hours"),
        CheckConstraint("flood_wait_count >= 0", name="ck_warmup_session_flood_wait_count"),
        CheckConstraint("consecutive_failures >= 0", name="ck_warmup_session_consecutive_failures"),
        Index("ix_warmup_session_workspace_id", "workspace_id"),
        Index("ix_warmup_session_account_id", "account_id"),
        Index("ix_warmup_session_status", "status"),
        Index(
            "ix_warmup_session_due",
            "next_step_at",
            postgresql_where=text("status IN ('scheduled', 'active')"),
            sqlite_where=text("status IN ('scheduled', 'active')"),
        ),
        Index(
            "ux_warmup_session_active_account",
            "workspace_id",
            "account_id",
            unique=True,
            postgresql_where=text(
                "status IN ('validating', 'scheduled', 'active', 'paused_risk', 'paused_manual')"
            ),
            sqlite_where=text(
                "status IN ('validating', 'scheduled', 'active', 'paused_risk', 'paused_manual')"
            ),
        ),
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
    strategy_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("warmup_strategy.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=WarmupStatus.DRAFT)
    current_day: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cadence_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    next_step_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_step_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    flood_wait_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    execution_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default=WarmupExecutionMode.DRY_RUN
    )
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_micro_session_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_micro_session_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cold_soak_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    daily_counters_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    trusted_peer_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    proxy_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    personality_seed_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    disabled_actions_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False, default="warming")
    strategy_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    account: Mapped[Account] = relationship(back_populates="warmup_sessions")
    strategy: Mapped[WarmupStrategy] = relationship(back_populates="sessions")
    events: Mapped[list[WarmupEvent]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    task_runs: Mapped[list[WarmupTaskRun]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class WarmupEvent(Base):
    __tablename__ = "warmup_event"
    __table_args__ = (
        Index("ix_warmup_event_workspace_id", "workspace_id"),
        Index("ix_warmup_event_session_created", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("warmup_session.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    session: Mapped[WarmupSession] = relationship(back_populates="events")


class WarmupTaskRun(Base):
    __tablename__ = "warmup_task_run"
    __table_args__ = (
        CheckConstraint("day BETWEEN 0 AND 30", name="ck_warmup_task_run_day"),
        CheckConstraint(
            "status IN ('started', 'completed', 'skipped', 'failed')",
            name="ck_warmup_task_run_status",
        ),
        UniqueConstraint(
            "session_id", "day", "task_type", name="uq_warmup_task_run_session_day_type"
        ),
        Index("ix_warmup_task_run_workspace_id", "workspace_id"),
        Index("ix_warmup_task_run_session_id", "session_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("warmup_session.id"), nullable=False
    )
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[WarmupSession] = relationship(back_populates="task_runs")


class WarmupTrustedPeer(Base):
    __tablename__ = "warmup_trusted_peer"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "account_id", name="uq_warmup_trusted_peer_workspace_account"
        ),
        Index("ix_warmup_trusted_peer_workspace_eligible", "workspace_id", "eligible_from"),
        CheckConstraint(
            "max_active_contacts >= 0", name="ck_warmup_trusted_peer_max_active_contacts"
        ),
        CheckConstraint("current_contacts >= 0", name="ck_warmup_trusted_peer_current_contacts"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False)
    eligible_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_active_contacts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    current_contacts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class WarmupIsolationClaim(Base):
    __tablename__ = "warmup_isolation_claim"

    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    held_by: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


# jscpd:ignore-end
