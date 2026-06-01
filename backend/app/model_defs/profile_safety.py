from __future__ import annotations

# ruff: noqa: F403,F405
# jscpd:ignore-start

from app.models import *


class AccountImportBatch(Base):
    __tablename__ = "account_import_batch"
    __table_args__ = (
        Index("ix_account_import_batch_workspace_status", "workspace_id", "status"),
        Index("ix_account_import_batch_created", "workspace_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="uploaded")
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list[AccountImportItem]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="AccountImportItem.created_at",
    )


class AccountImportItem(Base):
    __tablename__ = "account_import_item"
    __table_args__ = (
        Index("ix_account_import_item_batch_status", "batch_id", "status"),
        Index("ix_account_import_item_workspace_status", "workspace_id", "status"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    batch_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account_import_batch.id"), nullable=False, index=True
    )
    account_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("account.id"), nullable=True
    )
    source_ref_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    phone_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    username_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    validation_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    # jscpd:ignore-end

    batch: Mapped[AccountImportBatch] = relationship(back_populates="items")


class AccountProfileState(Base):
    __tablename__ = "account_profile_state"

    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), primary_key=True)
    telegram_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_photo_asset_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    account: Mapped[Account] = relationship(back_populates="profile_state")


class AccountProfileAudioState(Base):
    __tablename__ = "account_profile_audio_state"

    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), primary_key=True)
    telegram_audio_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    performer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_asset_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    raw_tdlib_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    account: Mapped[Account] = relationship(back_populates="profile_audio_state")


class AccountStoryPost(Base):
    __tablename__ = "account_story_post"
    __table_args__ = (
        UniqueConstraint("job_id", "step_key", name="uq_account_story_post_job_step"),
        Index("ix_story_post_account_status_created", "account_id", "status", "created_at"),
        Index("ix_story_post_account_asset", "account_id", "asset_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False)
    job_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    step_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    story_poster_chat_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_story_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    temporary_story_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    media_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    privacy_preset: Mapped[str] = mapped_column(String(64), nullable=False, default="contacts")
    active_period_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=86400)
    protect_content: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_be_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="posted")
    failure_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_tdlib_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    account: Mapped[Account] = relationship(back_populates="story_posts")


class AccountStoryDraft(Base):
    __tablename__ = "account_story_draft"
    __table_args__ = (
        Index("ix_story_draft_account_updated", "account_id", "updated_at"),
        Index("ix_story_draft_account_asset", "account_id", "asset_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False)
    asset_id: Mapped[str] = mapped_column(UUIDString, nullable=False)
    media_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    privacy_preset: Mapped[str] = mapped_column(String(64), nullable=False, default="contacts")
    active_period_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=86400)
    protect_content: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    validation_status: Mapped[str] = mapped_column(String(64), nullable=False, default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    account: Mapped[Account] = relationship(back_populates="story_drafts")


class AccountSafetySnapshot(Base):
    __tablename__ = "account_safety_snapshot"

    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), primary_key=True)
    health_status: Mapped[str] = mapped_column(String(64), nullable=False)
    overall_risk_level: Mapped[str] = mapped_column(String(64), nullable=False)
    validity_status: Mapped[str] = mapped_column(String(64), nullable=False)
    capabilities_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    risk_by_operation_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reasons_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    signals_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="db_snapshot")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AccountValidityCheckRun(Base):
    __tablename__ = "account_validity_check_run"
    __table_args__ = (Index("ix_validity_check_account_started", "account_id", "started_at"),)

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account.id"), nullable=False, index=True
    )
    mode: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_class: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AccountOperationCooldown(Base):
    __tablename__ = "account_operation_cooldown"
    __table_args__ = (
        Index("ix_cooldown_account_op_retry", "account_id", "operation", "retry_after_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account.id"), nullable=False, index=True
    )
    operation: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retry_after_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    source_job_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    source_step_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AccountSafetyOverride(Base):
    __tablename__ = "account_safety_override"
    __table_args__ = (
        Index(
            "ix_override_workspace_account_op_until",
            "workspace_id",
            "account_id",
            "operation",
            "allowed_until",
        ),
        Index("ix_override_account_op_until", "account_id", "operation", "allowed_until"),
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
    operation: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_blockers_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    allowed_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AccountOperationLog(Base):
    __tablename__ = "account_operation_log"
    __table_args__ = (
        Index("ix_operation_log_account_created", "account_id", "created_at"),
        Index("ix_operation_log_type_status_created", "operation_type", "status", "created_at"),
        Index("ix_operation_log_workspace_created", "workspace_id", "created_at"),
        Index(
            "ix_operation_log_ws_type_status_created",
            "workspace_id",
            "operation_type",
            "status",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("workspace.id"),
        nullable=False,
        default=DEFAULT_LOCAL_WORKSPACE_ID,
        index=True,
    )
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    operation_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="info")
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_class: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    job_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    step_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AccountProxy(Base):
    __tablename__ = "account_proxy"

    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), primary_key=True)
    proxy_type: Mapped[str] = mapped_column(String(16), nullable=False)
    proxy_category: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ProxyCategory.UNKNOWN
    )
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_check_scope: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    tdlib_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tdlib_last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tdlib_last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
