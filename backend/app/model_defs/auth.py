from __future__ import annotations

# ruff: noqa: F403,F405
# jscpd:ignore-start

from app.models import *


class AccountAuthAttempt(Base):
    __tablename__ = "account_auth_attempt"
    __table_args__ = (
        Index("ix_auth_attempt_account_kind_created", "account_id", "attempt_kind", "created_at"),
        Index("ix_auth_attempt_ref_kind_created", "external_ref", "attempt_kind", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    attempt_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(128), nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    account: Mapped[Account] = relationship(back_populates="auth_attempts")


class AuthBatch(Base):
    __tablename__ = "auth_batch"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "idempotency_key", name="uq_auth_batch_workspace_idempotency_key"
        ),
        Index("ix_auth_batch_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, default=DEFAULT_LOCAL_WORKSPACE_ID
    )
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default=AuthBatchStatus.PENDING)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancelled_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_running_commands: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    max_waiting_input: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_total_active: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list[AuthBatchItem]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", order_by="AuthBatchItem.position"
    )
    events: Mapped[list[AuthBatchEvent]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class AuthBatchItem(Base):
    __tablename__ = "auth_batch_item"
    __table_args__ = (
        UniqueConstraint("batch_id", "position", name="uq_auth_batch_item_batch_position"),
        Index("ix_auth_batch_item_batch_status", "batch_id", "status"),
        Index("ix_auth_batch_item_lock_expires", "lock_expires_at"),
        Index("ix_auth_batch_item_phone_status", "phone_number", "status"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    batch_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("auth_batch.id"), nullable=False)
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(64), nullable=False, default=AuthBatchItemStatus.QUEUED
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resend_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    code_error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    password_error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lock_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    batch: Mapped[AuthBatch] = relationship(back_populates="items")
    account: Mapped[Account] = relationship()
    attempts: Mapped[list[AuthAttempt]] = relationship(
        back_populates="batch_item", cascade="all, delete-orphan"
    )
    events: Mapped[list[AuthBatchEvent]] = relationship(back_populates="batch_item")


class AuthAttempt(Base):
    __tablename__ = "auth_attempt"
    __table_args__ = (
        UniqueConstraint(
            "batch_item_id", "attempt_number", "kind", name="uq_auth_attempt_item_number_kind"
        ),
        Index("ix_auth_attempt_batch_item", "batch_item_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    batch_item_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("auth_batch_item.id"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(64), nullable=False, default=AuthAttemptStatus.STARTED
    )
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    batch_item: Mapped[AuthBatchItem] = relationship(back_populates="attempts")


class AuthBatchEvent(Base):
    __tablename__ = "auth_batch_event"
    __table_args__ = (
        Index("ix_auth_batch_event_batch_created", "batch_id", "created_at"),
        Index("ix_auth_batch_event_item_created", "batch_item_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    batch_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("auth_batch.id"), nullable=False)
    batch_item_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("auth_batch_item.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    batch: Mapped[AuthBatch] = relationship(back_populates="events")
    batch_item: Mapped[AuthBatchItem | None] = relationship(back_populates="events")


class IdempotencyKey(Base):
    __tablename__ = "idempotency_key"
    __table_args__ = (Index("ix_idempotency_key_expires", "expires_at"),)

    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), primary_key=True, default=DEFAULT_LOCAL_WORKSPACE_ID
    )
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    operation: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str] = mapped_column(UUIDString, nullable=False)
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# jscpd:ignore-end
