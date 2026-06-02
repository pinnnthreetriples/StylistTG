from __future__ import annotations

# ruff: noqa: F403,F405

from app.models import *


class AccountOnboardingBatch(Base):
    __tablename__ = "account_onboarding_batch"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_account_onboarding_batch_workspace_idempotency",
        ),
        Index("ix_account_onboarding_batch_workspace_status", "workspace_id", "status"),
        Index("ix_account_onboarding_batch_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="created")
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    consent_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consent_actor_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    consent_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ready_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requires_reauth_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list[AccountOnboardingItem]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="AccountOnboardingItem.position",
    )
    artifacts: Mapped[list[AccountOnboardingArtifact]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )
    events: Mapped[list[AccountOnboardingEvent]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class AccountOnboardingItem(Base):
    __tablename__ = "account_onboarding_item"
    __table_args__ = (
        UniqueConstraint("batch_id", "position", name="uq_account_onboarding_item_batch_position"),
        Index("ix_account_onboarding_item_workspace_batch", "workspace_id", "batch_id"),
        Index("ix_account_onboarding_item_batch_status", "batch_id", "status"),
        Index(
            "ix_account_onboarding_item_workspace_phone_hash",
            "workspace_id",
            "phone_normalized_hash",
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    batch_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account_onboarding_batch.id"), nullable=False
    )
    account_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("account.id"), nullable=True
    )
    auth_session_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("telegram_auth_session.id"), nullable=True
    )
    artifact_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("account_onboarding_artifact.id"), nullable=True
    )
    source_ref_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    phone_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone_normalized_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    username_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_user_id_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    validation_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="low")
    requires_reauth: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    batch: Mapped[AccountOnboardingBatch] = relationship(back_populates="items")
    artifact: Mapped[AccountOnboardingArtifact | None] = relationship(foreign_keys=[artifact_id])
    account: Mapped[Account | None] = relationship()


class AccountOnboardingArtifact(Base):
    __tablename__ = "account_onboarding_artifact"
    __table_args__ = (
        Index("ix_account_onboarding_artifact_workspace_status", "workspace_id", "status"),
        Index("ix_account_onboarding_artifact_expires", "expires_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    batch_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("account_onboarding_batch.id"), nullable=True
    )
    item_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("account_onboarding_item.id"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type_detected: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="uploaded")
    created_by_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    batch: Mapped[AccountOnboardingBatch | None] = relationship(back_populates="artifacts")


class AccountOnboardingEvent(Base):
    __tablename__ = "account_onboarding_event"
    __table_args__ = (
        Index("ix_account_onboarding_event_batch_created", "batch_id", "created_at"),
        Index("ix_account_onboarding_event_item_created", "item_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    batch_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("account_onboarding_batch.id"), nullable=False
    )
    item_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("account_onboarding_item.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    safe_payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    batch: Mapped[AccountOnboardingBatch] = relationship(back_populates="events")
