from __future__ import annotations

# ruff: noqa: F403,F405

from app.models import *

class User(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        UniqueConstraint(
            "external_auth_provider", "external_auth_user_id", name="uq_user_external_auth"
        ),
        Index("ix_user_email", "email"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_auth_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    external_auth_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=UserStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owned_workspaces: Mapped[list[Workspace]] = relationship(back_populates="owner")
    memberships: Mapped[list[WorkspaceMember]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Workspace(Base):
    __tablename__ = "workspace"
    __table_args__ = (UniqueConstraint("slug", name="uq_workspace_slug"),)

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=WorkspaceStatus.ACTIVE)
    safety_pipeline_v2_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    notification_webhook_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    owner: Mapped[User] = relationship(
        back_populates="owned_workspaces", foreign_keys=[owner_user_id]
    )
    members: Mapped[list[WorkspaceMember]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class WorkspaceMember(Base):
    __tablename__ = "workspace_member"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member_workspace_user"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    workspace: Mapped[Workspace] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_workspace_created", "workspace_id", "created_at"),)

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SensitiveAuditEvent(Base):
    __tablename__ = "sensitive_audit_event"
    __table_args__ = (
        Index("ix_sensitive_audit_workspace_created", "workspace_id", "created_at"),
        Index("ix_sensitive_audit_account_created", "account_id", "created_at"),
        Index("ix_sensitive_audit_action_created", "action", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False, index=True
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("app_user.id"), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(String(64), nullable=False, default="user")
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True)
    account_id: Mapped[str | None] = mapped_column(UUIDString, nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AdminNotificationLog(Base):
    __tablename__ = "admin_notification_log"
    __table_args__ = (
        Index(
            "ix_admin_notification_log_ws_trigger_time",
            "workspace_id",
            "trigger_code",
            "triggered_at",
        ),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    trigger_code: Mapped[str] = mapped_column(String(64), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    delivered_channels: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )


class WorkspaceSafetyPolicy(Base):
    __tablename__ = "workspace_safety_policy"
    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_workspace_safety_policy_workspace"),
        CheckConstraint(
            "mode in ('conservative', 'balanced', 'aggressive')",
            name="ck_workspace_safety_policy_mode",
        ),
        CheckConstraint(
            "consecutive_failure_threshold IS NULL OR "
            "consecutive_failure_threshold BETWEEN 1 AND 20",
            name="ck_workspace_safety_policy_consecutive_failure_threshold",
        ),
        Index("ix_workspace_safety_policy_workspace_id", "workspace_id"),
    )

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("workspace.id"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="balanced")
    delay_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    typing_chars_per_minute_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    typing_chars_per_minute_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    profile_view_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    scroll_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    typo_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    message_deletion_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.02)
    quiet_hours_local_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quiet_hours_local_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    require_warmup_before_commenting: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    min_warmup_days: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    require_healthy_proxy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    min_account_age_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    auto_pause_on_flood_wait_count: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    auto_pause_on_deleted_comments_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5
    )
    quarantine_hours_on_flood_wait: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    consecutive_failure_threshold: Mapped[int | None] = mapped_column(
        Integer, nullable=True, server_default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
