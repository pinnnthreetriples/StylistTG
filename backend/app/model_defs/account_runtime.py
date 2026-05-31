from __future__ import annotations

# ruff: noqa: F403,F405
# jscpd:ignore-start

from app.models import *


class Account(Base):
    __tablename__ = "account"
    __table_args__ = (
        UniqueConstraint("workspace_id", "external_ref", name="uq_account_workspace_external_ref"),
        CheckConstraint(
            "origin IN ('imported','bought','created')",
            name="ck_accounts_origin_valid",
        ),
        CheckConstraint(
            "terminal_status IN ('none','banned','deleted','suspended')",
            name="ck_accounts_terminal_status_valid",
        ),
        Index("ix_account_workspace_updated", "workspace_id", "updated_at"),
        Index(
            "ix_accounts_safety_grace_until",
            "safety_grace_period_until",
            postgresql_where=text("safety_grace_period_until IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, default=DEFAULT_LOCAL_WORKSPACE_ID
    )
    external_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pinned_channel_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_source: Mapped[str] = mapped_column(String(64), nullable=False, default="otp")
    origin: Mapped[str] = mapped_column(
        String(16), nullable=False, default="imported", server_default="imported"
    )
    account_state: Mapped[str] = mapped_column(
        String(64), nullable=False, default=AccountState.REGISTERED
    )
    terminal_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="none", server_default="none"
    )
    safety_grace_period_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    runtime_state: Mapped[AccountRuntimeState] = relationship(
        back_populates="account", cascade="all, delete-orphan", uselist=False
    )
    profile_state: Mapped[AccountProfileState | None] = relationship(
        back_populates="account", cascade="all, delete-orphan", uselist=False
    )
    profile_audio_state: Mapped[AccountProfileAudioState | None] = relationship(
        back_populates="account", cascade="all, delete-orphan", uselist=False
    )
    story_posts: Mapped[list[AccountStoryPost]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    story_drafts: Mapped[list[AccountStoryDraft]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    safety_snapshot: Mapped[AccountSafetySnapshot | None] = relationship(
        cascade="all, delete-orphan", uselist=False
    )
    validity_check_runs: Mapped[list[AccountValidityCheckRun]] = relationship(
        cascade="all, delete-orphan"
    )
    operation_cooldowns: Mapped[list[AccountOperationCooldown]] = relationship(
        cascade="all, delete-orphan"
    )
    safety_overrides: Mapped[list[AccountSafetyOverride]] = relationship(
        cascade="all, delete-orphan"
    )
    operation_logs: Mapped[list[AccountOperationLog]] = relationship(cascade="all, delete-orphan")
    proxy: Mapped[AccountProxy | None] = relationship(cascade="all, delete-orphan", uselist=False)
    jobs: Mapped[list[Job]] = relationship(back_populates="account")
    auth_attempts: Mapped[list[AccountAuthAttempt]] = relationship(back_populates="account")
    deletion_requests: Mapped[list[AccountDeletionRequest]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    export_requests: Mapped[list[AccountExportRequest]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    telegram_auth_sessions: Mapped[list[TelegramAuthSession]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    warmup_sessions: Mapped[list[WarmupSession]] = relationship(back_populates="account")


class BoughtOnboardingState(Base):
    __tablename__ = "bought_onboarding_state"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "account_id",
            name="uq_bought_onboarding_state_ws_account",
        ),
        CheckConstraint(
            "current_step IN ('enable_2fa','terminate_other_sessions','rest_period','ggr_precheck','completed')",
            name="ck_bought_onboarding_state_current_step",
        ),
        Index("ix_bought_onboarding_state_workspace_account", "workspace_id", "account_id"),
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
    current_step: Mapped[str] = mapped_column(String(64), nullable=False, default="enable_2fa")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class AccountLifecycleEvent(Base):
    __tablename__ = "account_lifecycle_event"
    __table_args__ = (
        Index("ix_account_lifecycle_workspace_created", "workspace_id", "created_at"),
        Index("ix_account_lifecycle_account_created", "account_id", "created_at"),
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
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    request_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AccountDeletionRequest(Base):
    __tablename__ = "account_deletion_request"
    __table_args__ = (
        Index("ix_account_deletion_workspace_status", "workspace_id", "status"),
        Index("ix_account_deletion_account_status", "account_id", "status"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account.id"), nullable=False, index=True
    )
    requested_by_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="requested")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    dry_run_result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    execution_result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    account: Mapped[Account] = relationship(back_populates="deletion_requests")


class AccountExportRequest(Base):
    __tablename__ = "account_export_request"
    __table_args__ = (
        Index("ix_account_export_workspace_status", "workspace_id", "status"),
        Index("ix_account_export_account_created", "account_id", "requested_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account.id"), nullable=False, index=True
    )
    requested_by_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="requested")
    export_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    export_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    export_content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped[Account] = relationship(back_populates="export_requests")


class AccountRuntimeState(Base):
    __tablename__ = "account_runtime_state"

    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), primary_key=True)
    session_present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    authorized_last_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    runtime_health: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    reauth_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lock_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lock_epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recovery_marker: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    account: Mapped[Account] = relationship(back_populates="runtime_state")


class TelegramAuthSession(Base):
    __tablename__ = "telegram_auth_session"
    __table_args__ = (
        Index("ix_telegram_auth_session_workspace_status", "workspace_id", "status"),
        Index("ix_telegram_auth_session_account_created", "account_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    account_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("account.id"), nullable=True, index=True
    )
    phone_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="created")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="new_auth")
    tdlib_storage_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requires_code: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped[Account | None] = relationship(back_populates="telegram_auth_sessions")


# jscpd:ignore-end
