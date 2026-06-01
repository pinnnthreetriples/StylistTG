from __future__ import annotations

# pyright: reportPrivateUsage=false, reportUndefinedVariable=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportUntypedBaseClass=false, reportUntypedFunctionDecorator=false, reportInvalidTypeForm=false

# ruff: noqa: F403,F405

from app.schemas import *
from app.schemas import _serialize_utc_datetime


class ExecutionPolicyRead(BaseModel):
    profile_job_cooldown_seconds: int
    profile_job_cooldown_enabled: bool
    allowed_profile_job_cooldown_seconds: list[int]
    profile_update_cooldown_seconds: int
    username_cooldown_seconds: int
    profile_photo_cooldown_seconds: int
    profile_music_cooldown_seconds: int
    story_post_cooldown_seconds: int
    story_delete_cooldown_seconds: int
    unknown_capability_policy: str
    recent_failure_policy: str
    fresh_validity_required: str
    fresh_validity_max_age_minutes: int
    manual_hard_blocker_override_enabled: bool
    non_overridable_blockers: list[str]


class ExecutionPolicyUpdate(BaseModel):
    profile_job_cooldown_seconds: ProfileCooldownSeconds = Field(
        default=cast(ProfileCooldownSeconds, None)
    )
    profile_update_cooldown_seconds: OperationCooldownSeconds = Field(
        default=cast(OperationCooldownSeconds, None)
    )
    username_cooldown_seconds: OperationCooldownSeconds = Field(
        default=cast(OperationCooldownSeconds, None)
    )
    profile_photo_cooldown_seconds: OperationCooldownSeconds = Field(
        default=cast(OperationCooldownSeconds, None)
    )
    profile_music_cooldown_seconds: OperationCooldownSeconds = Field(
        default=cast(OperationCooldownSeconds, None)
    )
    story_post_cooldown_seconds: OperationCooldownSeconds = Field(
        default=cast(OperationCooldownSeconds, None)
    )
    story_delete_cooldown_seconds: OperationCooldownSeconds = Field(
        default=cast(OperationCooldownSeconds, None)
    )
    unknown_capability_policy: Literal["warning_only", "block_live_execution"] = Field(
        default=cast(Literal["warning_only", "block_live_execution"], None)
    )
    recent_failure_policy: Literal["warning_only", "cooldown"] = Field(
        default=cast(Literal["warning_only", "cooldown"], None)
    )
    fresh_validity_required: Literal["never", "if_stale", "always_for_live"] = Field(
        default=cast(Literal["never", "if_stale", "always_for_live"], None)
    )
    fresh_validity_max_age_minutes: Annotated[int, Field(ge=1, le=1440)] = Field(
        default=cast(int, None)
    )
    manual_hard_blocker_override_enabled: StrictBool = Field(default=cast(StrictBool, None))

    @field_validator(
        "profile_job_cooldown_seconds",
        "profile_update_cooldown_seconds",
        "username_cooldown_seconds",
        "profile_photo_cooldown_seconds",
        "profile_music_cooldown_seconds",
        "story_post_cooldown_seconds",
        "story_delete_cooldown_seconds",
        "fresh_validity_max_age_minutes",
        mode="before",
    )
    @classmethod
    def _reject_boolean_ints(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean values are not valid integers")
        return value


class LivePreflightRead(BaseModel):
    tdjson_present: bool
    tdlib_credentials_present: bool
    postgres_reachable: bool
    redis_reachable: bool
    storage_writable: bool
    rq_worker_expected: bool
    rq_worker_status: str | None = None
    profile_worker_status: str | None = None
    auth_worker_status: str | None = None
    overall_status: str


class OtpStartRequest(BaseModel):
    phone_number: str = Field(pattern=r"^\+[1-9]\d{7,14}$")


class OtpConfirmRequest(BaseModel):
    account_id: str
    code: str


class PasswordSubmitRequest(BaseModel):
    account_id: str
    password: str


class AuthStateRead(BaseModel):
    account_id: str
    external_ref: str
    telegram_user_id: str | None
    orchestration_state: str
    auth_step_status: str
    needs_code: bool
    needs_password: bool = False
    password_hint: str | None = None
    session_present: bool
    runtime_health: str
    reauth_required: bool
    recovery_marker: str | None
    authorized_last_confirmed_at: datetime | None
    error: str | None = None


class AuthRuntimeModeRead(BaseModel):
    tdlib_use_test_dc: bool
    tdlib_production_auth_enabled: bool


class AuthRuntimeModeUpdate(BaseModel):
    tdlib_use_test_dc: StrictBool


class AuthBatchPhoneInput(BaseModel):
    phone_number: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    label: str | None = None


class AuthBatchValidatePhoneInput(BaseModel):
    phone_number: str = Field(min_length=1)
    label: str | None = None


class AuthBatchValidateRequest(BaseModel):
    items: list[AuthBatchValidatePhoneInput] = Field(min_length=1)


class AuthBatchValidItemRead(BaseModel):
    phone_number: str
    label: str | None = None
    position: int


class AuthBatchInvalidItemRead(BaseModel):
    input: str
    label: str | None = None
    position: int
    error: str


class AuthBatchPhoneConflictRead(BaseModel):
    phone_number: str
    label: str | None = None
    position: int
    account_id: str | None = None
    batch_item_id: str | None = None
    batch_id: str | None = None


class AuthBatchValidateRead(BaseModel):
    valid_items: list[AuthBatchValidItemRead]
    invalid_items: list[AuthBatchInvalidItemRead]
    duplicates: list[AuthBatchPhoneConflictRead]
    existing_accounts: list[AuthBatchPhoneConflictRead]
    active_batch_conflicts: list[AuthBatchPhoneConflictRead]


class AuthBatchCreate(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=128)
    label: str | None = None
    items: list[AuthBatchPhoneInput] = Field(min_length=1)
    max_running_commands: int = Field(default=2, ge=1, le=12)
    max_waiting_input: int = Field(default=5, ge=1, le=12)
    max_total_active: int = Field(default=6, ge=1, le=12)

    @field_validator("max_running_commands", "max_waiting_input", "max_total_active", mode="before")
    @classmethod
    def _reject_boolean_ints(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean values are not valid integers")
        return value


class AuthBatchRead(BaseModel):
    id: str
    label: str | None
    status: str
    total_count: int
    success_count: int
    failed_count: int
    cancelled_count: int
    skipped_count: int
    max_running_commands: int
    max_waiting_input: int
    max_total_active: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @field_serializer("created_at", "started_at", "finished_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return _serialize_utc_datetime(value)


class AuthBatchItemRead(BaseModel):
    id: str
    batch_id: str
    account_id: str
    phone_number: str | None
    phone_hint: str
    label: str | None
    position: int
    status: str
    attempt_count: int
    resend_count: int
    code_error_count: int
    password_error_count: int
    code_expires_at: datetime | None
    next_retry_at: datetime | None
    error_code: str | None
    error_message: str | None
    updated_at: datetime
    authorized_at: datetime | None

    @field_serializer("code_expires_at", "next_retry_at", "updated_at", "authorized_at")
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return _serialize_utc_datetime(value)


class AuthBatchSnapshotRead(BaseModel):
    batch: AuthBatchRead
    items: list[AuthBatchItemRead]
    server_time: datetime
    poll_again_in_ms: int

    @field_serializer("server_time")
    def _serialize_datetime(self, value: datetime) -> str:
        return _serialize_utc_datetime(value)


class AuthBatchPollRead(BaseModel):
    batch: AuthBatchRead
    items: list[AuthBatchItemRead]
    server_time: datetime
    poll_again_in_ms: int

    @field_serializer("server_time")
    def _serialize_datetime(self, value: datetime) -> str:
        return _serialize_utc_datetime(value)


class AuthBatchSubmitCodeRequest(BaseModel):
    code: str
    idempotency_key: str

    def __repr__(self) -> str:
        return f"AuthBatchSubmitCodeRequest(code=***REDACTED***, idempotency_key={self.idempotency_key!r})"


class AuthBatchSubmitPasswordRequest(BaseModel):
    password: str
    idempotency_key: str

    def __repr__(self) -> str:
        return f"AuthBatchSubmitPasswordRequest(password=***REDACTED***, idempotency_key={self.idempotency_key!r})"


class AuthBatchEventRead(BaseModel):
    id: str
    batch_id: str
    batch_item_id: str | None
    event_type: str
    actor: str
    payload_json: dict[str, Any]
    created_at: datetime
