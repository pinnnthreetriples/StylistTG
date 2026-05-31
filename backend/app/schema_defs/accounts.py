from __future__ import annotations

# ruff: noqa: F403,F405

from app.schemas import *
from app.schemas import _empty_readiness_risk_items, _serialize_utc_datetime

class AccountCreate(BaseModel):
    external_ref: str = Field(min_length=1)
    telegram_user_id: str | None = Field(default=None, min_length=1)
    origin: Literal["imported", "bought", "created"] = "imported"


class AccountWarmupInfoRead(BaseModel):
    session_id: str | None = None
    status: str | None = None
    current_day: int | None = None
    is_locked: bool = False


class CurrentUserRead(BaseModel):
    user_id: str
    email: str
    display_name: str | None
    workspace_id: str
    workspace_name: str
    role: str
    auth_source: str


class WorkspaceRead(BaseModel):
    id: str
    name: str
    slug: str
    owner_user_id: str
    status: str
    safety_pipeline_v2_enabled: bool
    notification_webhook_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at")
    def _serialize_datetime(self, value: datetime) -> str:
        return _serialize_utc_datetime(value)


class WorkspaceFeatureFlagsUpdate(BaseModel):
    safety_pipeline_v2_enabled: StrictBool

    model_config = ConfigDict(extra="forbid")


class WorkspaceNotificationSettingsUpdate(BaseModel):
    notification_webhook_url: str | None = Field(
        default=None,
        max_length=512,
        pattern=r"^https://",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("notification_webhook_url")
    @classmethod
    def _validate_https_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.startswith("https://"):
            raise ValueError("notification_webhook_url must be an HTTPS URL")
        return value


class AccountRead(BaseModel):
    id: str
    external_ref: str
    telegram_user_id: str | None
    auth_source: str
    origin: Literal["imported", "bought", "created"]
    account_state: str
    terminal_status: TerminalStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at")
    def _serialize_datetime(self, value: datetime) -> str:
        return _serialize_utc_datetime(value)


class AccountListItemRead(BaseModel):
    account_id: str
    display_name: str | None
    username: str | None
    phone_number: str
    telegram_user_id: str | None
    origin: Literal["imported", "bought", "created"]
    account_state: str
    terminal_status: TerminalStatus
    runtime_health: str
    is_execution_usable: bool
    is_test_dc: bool
    profile_photo_asset_id: str | None
    updated_at: datetime
    warmup: AccountWarmupInfoRead | None = None


class RuntimeRefreshRead(BaseModel):
    account_id: str
    account_state: str
    runtime_health: str
    is_execution_usable: bool
    last_error_code: str | None
    last_error_class: str | None
    refreshed_at: datetime


class AccountRuntimeDiagnosticsRead(BaseModel):
    account_id: str
    account_state: str
    runtime_health: str
    reauth_required: bool
    authorized_last_confirmed_at: datetime | None
    can_start_profile_job: bool
    last_error_code: str | None
    last_error_class: str | None
    tdlib_configured: bool
    manual_intervention_required: bool
    recovery_marker: str | None
    lock_owner: str | None
    lock_epoch: int
    diagnostic_timestamp: str


class AccountReadinessRiskReasonRead(BaseModel):
    code: str
    severity: Literal["info", "warning", "critical"]
    message: str


class AccountReadinessRiskRead(BaseModel):
    account_id: str
    score: int
    level: Literal["low", "medium", "high", "critical"]
    reasons: list[AccountReadinessRiskReasonRead]
    recommended_action: str | None = None
    computed_at: datetime


class AccountReadinessRiskSummaryRead(BaseModel):
    total: int
    low: int
    medium: int
    high: int
    critical: int
    reauth_required: int
    missing_session: int
    runtime_unhealthy: int
    proxy_problem: int
    items: list[AccountReadinessRiskRead] = Field(default_factory=_empty_readiness_risk_items)
    computed_at: datetime


class SensitiveAuditEventRead(BaseModel):
    id: str
    workspace_id: str
    actor_user_id: str | None = None
    actor_type: str
    action: str
    entity_type: str
    entity_id: str | None = None
    account_id: str | None = None
    request_id: str | None = None
    reason: str | None = None
    override_reason: str | None = None
    risk_level: str | None = None
    risk_score: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SensitiveAuditEventPageRead(BaseModel):
    items: list[SensitiveAuditEventRead]
    total: int
    limit: int
    offset: int


class ActionGateRead(BaseModel):
    account_id: str
    action_type: str
    allowed: bool
    requires_override: bool
    blocked: bool
    risk_level: str
    risk_score: int
    reasons: list[AccountReadinessRiskReasonRead]
    required_override_reason: bool


class QueueDescriptorRead(BaseModel):
    name: str
    purpose: str
    live_execution_default: bool


class WorkerDiagnosticsRead(BaseModel):
    queues: list[QueueDescriptorRead]
    mode: str
    redis: dict[str, Any]
    scheduler: dict[str, Any]
    reaper: dict[str, Any]
    rate_limits: dict[str, int]
    tdlib: dict[str, Any]


class TdlibRuntimeStatusRead(BaseModel):
    configured: bool
    library_configured: bool
    library_loadable: bool
    live_enabled: bool
    runtime_mode: str
    api_id_configured: bool
    api_hash_configured: bool
    readonly_smoke_available: bool
    error_code: str | None = None
