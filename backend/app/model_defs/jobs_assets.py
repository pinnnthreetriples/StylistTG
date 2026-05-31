from __future__ import annotations

# ruff: noqa: F403,F405

from app.models import *

class Job(Base):
    __tablename__ = "job"
    __table_args__ = (
        Index("ix_job_account_queued", "account_id", "queued_at"),
        Index("ix_job_workspace_account_queued", "workspace_id", "account_id", "queued_at"),
        Index("ix_job_account_intent_state", "account_id", "execution_intent_hash", "job_state"),
        Index("ix_job_account_finished", "account_id", "finished_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, default=DEFAULT_LOCAL_WORKSPACE_ID
    )
    account_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("account.id"), nullable=False)
    requested_by_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    approved_by_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    created_from: Mapped[str] = mapped_column(String(64), nullable=False, default="api")
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    job_state: Mapped[str] = mapped_column(String(64), nullable=False, default=JobState.QUEUED)
    workflow_type: Mapped[str] = mapped_column(String(64), nullable=False, default="profile_update")
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    execution_intent_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    job_payload_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    desired_state_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    capability_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    plan_json_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    compensation_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dedup_blocked_by_job_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    account: Mapped[Account] = relationship(back_populates="jobs")
    step_results: Mapped[list[JobStepResult]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobStepResult.started_at"
    )
    execution_events: Mapped[list[JobExecutionEvent]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobExecutionEvent.created_at"
    )


class JobExecutionEvent(Base):
    __tablename__ = "job_execution_event"
    __table_args__ = (
        Index("ix_job_execution_workspace_created", "workspace_id", "created_at"),
        Index("ix_job_execution_account_created", "account_id", "created_at"),
        Index("ix_job_execution_job_created", "job_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    job_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("job.id"), nullable=True, index=True
    )
    job_type: Mapped[str] = mapped_column(String(128), nullable=False)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    account_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    queue_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lock_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    risk_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    job: Mapped[Job | None] = relationship(back_populates="execution_events")


class JobStepResult(Base):
    __tablename__ = "job_step_result"
    __table_args__ = (
        Index("ix_job_step_result_job_started", "job_id", "started_at"),
        Index("ix_job_step_result_job_status_finished", "job_id", "status", "finished_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(UUIDString, ForeignKey("job.id"), nullable=False)
    step_key: Mapped[str] = mapped_column(String(128), nullable=False)
    step_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default=StepStatus.PLANNED)
    step_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capability_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    compensation_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    uncertain_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_attempted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_class: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    job: Mapped[Job] = relationship(back_populates="step_results")


class Asset(Base):
    __tablename__ = "asset"
    __table_args__ = (Index("ix_asset_workspace_storage", "workspace_id", "storage_backend"),)

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, default=DEFAULT_LOCAL_WORKSPACE_ID
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mime: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_backend: Mapped[str | None] = mapped_column(String(32), nullable=True)
    storage_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    normalized_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    normalized_content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    normalized_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    storage_migrated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RateLimitPersistentCounter(Base):
    __tablename__ = "rate_limit_persistent_counters"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "scope_type",
            "scope_id",
            "scope_key",
            "window_start",
            name="uq_rate_limit_persistent_counters_scope_window",
        ),
        Index(
            "ix_rate_limit_persistent_counters_scope",
            "workspace_id",
            "scope_type",
            "scope_id",
            "scope_key",
            "window_start",
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str] = mapped_column(UUIDString, nullable=False)
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
