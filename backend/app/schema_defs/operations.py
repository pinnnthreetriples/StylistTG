from __future__ import annotations

# ruff: noqa: F403,F405

from app.schemas import *
from app.schemas import _empty_import_items, _serialize_utc_datetime

class TelegramAuthSessionCreate(BaseModel):
    phone_number: str = Field(min_length=3, max_length=64)
    label: str | None = Field(default=None, max_length=255)
    proxy_id: str | None = None


class TelegramAuthCodeSubmit(BaseModel):
    code: str = Field(min_length=1, max_length=32)


class TelegramAuthPasswordSubmit(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class TelegramAuthSessionRead(BaseModel):
    id: str
    workspace_id: str
    account_id: str | None
    phone_hint: str | None
    label: str | None
    status: str
    source: str
    requires_code: bool
    requires_password: bool
    cooldown_until: datetime | None
    last_error_code: str | None
    last_error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    failed_at: datetime | None

    @field_serializer("cooldown_until", "created_at", "updated_at", "completed_at", "failed_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return _serialize_utc_datetime(value)


class AccountImportBatchCreate(BaseModel):
    source_type: Literal["tdlib-directory", "tdata", "session-file", "json-metadata"]
    label: str | None = Field(default=None, max_length=255)
    dry_run: StrictBool = True
    metadata: dict[str, Any] | None = None


class AccountImportBatchValidate(BaseModel):
    metadata: dict[str, Any] | None = None
    content_base64: str | None = Field(
        default=None,
        pattern=r"^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$",
    )


class AccountImportBatchConfirm(BaseModel):
    confirmation: Literal["IMPORT"]


class AccountImportItemRead(BaseModel):
    id: str
    account_id: str | None
    status: str
    phone_hint: str | None
    username_hint: str | None
    validation_code: str | None
    validation_message: str | None
    risk_level: str | None
    created_at: datetime
    updated_at: datetime


class AccountImportBatchRead(BaseModel):
    id: str
    workspace_id: str
    source_type: str
    status: str
    label: str | None
    dry_run: bool
    item_count: int
    created_at: datetime
    completed_at: datetime | None
    failed_at: datetime | None
    failure_code: str | None
    failure_message: str | None
    items: list[AccountImportItemRead] = Field(default_factory=_empty_import_items)


class RetryPolicyRead(BaseModel):
    retry: bool
    max_attempts: int
    interval_seconds: list[int]
    failure_ttl_seconds: int
    result_ttl_seconds: int
    error_category: str


class AccountValidityCheckRequest(BaseModel):
    mode: Literal["db_snapshot", "tdlib_readonly", "full_capability"] = "db_snapshot"


class AccountBatchSafetyPreviewRequest(BaseModel):
    account_ids: list[str] = Field(min_length=1, max_length=500)
    operation: str = "batch_operation"
    allow_warning_overrides: bool = False


class AccountBatchSafetyItemRead(BaseModel):
    account_id: str
    batch_status: str
    health_status: str
    risk_level: str
    reasons: list[AccountSafetyReasonRead]
    cooldowns: list[AccountOperationCooldownRead]


class AccountBatchSafetyPreviewRead(BaseModel):
    operation: str
    can_start: bool
    counts: dict[str, int]
    blocking_account_ids: list[str]
    warning_account_ids: list[str]
    items: list[AccountBatchSafetyItemRead]


class AccountSafetyOverrideCreate(BaseModel):
    operation: str
    reason: str = Field(min_length=3, max_length=1000)
    requested_blockers: list[str] = Field(default_factory=list)


class AccountSafetyOverrideRead(BaseModel):
    id: str
    account_id: str
    operation: str
    reason: str
    requested_blockers: list[str]
    allowed_until: datetime
    created_at: datetime


class AccountOperationLogRead(BaseModel):
    id: str
    account_id: str
    operation_type: str
    operation_key: str | None = None
    status: str
    severity: str
    source: str
    message: str
    error_code: str | None = None
    error_class: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
    job_id: str | None = None
    step_id: str | None = None
    created_at: datetime


class AccountOperationLogPageRead(BaseModel):
    items: list[AccountOperationLogRead]
    total: int
    limit: int
    offset: int


class AccountProxyUpsert(BaseModel):
    proxy_type: Literal["socks5", "http"]
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=1000)


class AccountProxyRead(BaseModel):
    account_id: str
    proxy_type: str
    host: str
    port: int
    username: str | None = None
    has_password: bool
    status: str
    last_checked_at: datetime | None = None
    last_check_scope: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    tdlib_verified_at: datetime | None = None
    tdlib_last_error_code: str | None = None
    tdlib_last_error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class AccountProxySummaryRead(BaseModel):
    account_id: str
    status: str
    proxy_type: str | None = None
    host: str | None = None
    port: int | None = None
    last_checked_at: datetime | None = None
    last_check_scope: str | None = None
    last_error_code: str | None = None
    tdlib_verified_at: datetime | None = None
    tdlib_last_error_code: str | None = None


class FieldErrorRead(BaseModel):
    field: str
    message: str


class ApiErrorRead(BaseModel):
    error_code: str
    error_class: str
    message: str
    details: dict[str, Any] | None
    field_errors: list[FieldErrorRead]
    request_id: str


class DiagnosticsRead(BaseModel):
    database: str
    redis: str
    tdlib: str


class ReadinessRead(BaseModel):
    status: str


class FrontendDiagnosticsDatabaseRead(BaseModel):
    status: str
    mode: str


class FrontendDiagnosticsRedisRead(BaseModel):
    status: str
    configured: bool


class FrontendDiagnosticsStorageRead(BaseModel):
    backend: str
    bucket_configured: bool
    signed_url_enabled: bool
    public_base_url_configured: bool


class FrontendDiagnosticsTdlibRead(BaseModel):
    status: str
    profile_execution_adapter: str
    live_enabled: bool
    runtime_mode: str = "mock"
    library_configured: bool = False
    library_loadable: bool = False
    api_id_configured: bool = False
    api_hash_configured: bool = False
    auth_worker_ready: bool = False
    readonly_smoke_available: bool = False
    session_root_configured: bool = False
    execution_plane_ready: bool = False
    error_code: str | None = None


class FrontendDiagnosticsWorkersRead(BaseModel):
    queues: list[str]
    mode: str
    scheduler_enabled: bool = False
    reaper_mode: str = "dry_run"


class FrontendDiagnosticsSummaryRead(BaseModel):
    app_env: str
    auth_mode: str
    db: FrontendDiagnosticsDatabaseRead
    redis: FrontendDiagnosticsRedisRead
    storage: FrontendDiagnosticsStorageRead
    tdlib: FrontendDiagnosticsTdlibRead
    workers: FrontendDiagnosticsWorkersRead
    generated_at: datetime
