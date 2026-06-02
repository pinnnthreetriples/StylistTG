from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contracts.types import UuidString

SourceType = Literal["phone", "phone_bulk", "json_metadata", "tdlib_directory", "tdata_archive", "session_file", "reauth"]


class OnboardingCapabilityRead(BaseModel):
    source_type: SourceType
    can_preview: bool
    can_validate_structure: bool
    can_materialize_session: bool
    requires_reauth: bool
    supports_bulk: bool
    supports_artifact_upload: bool
    risk_level: Literal["low", "medium", "high"]
    user_facing_support_level: Literal["full", "preview_only", "requires_reauth", "unsupported"]


class PhoneOnboardingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone_number: str = Field(min_length=1, max_length=64)
    label: str | None = Field(default=None, max_length=255)
    position: int = Field(default=0, ge=0)


class AccountOnboardingBatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=128)
    source_type: SourceType
    label: str | None = Field(default=None, max_length=255)
    phone_items: list[PhoneOnboardingInput] = Field(default_factory=list)
    metadata_json: Any | None = None
    artifact_id: UuidString | None = None
    filename: str | None = None

    @field_validator("phone_items")
    @classmethod
    def _limit_phone_items(cls, value: list[PhoneOnboardingInput]) -> list[PhoneOnboardingInput]:
        if len(value) > 500:
            raise ValueError("maximum 500 phone items")
        return value


class AccountOnboardingMutationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=128)


class AccountOnboardingValidateRequest(AccountOnboardingMutationRequest):
    pass


class AccountOnboardingConfirmRequest(AccountOnboardingMutationRequest):
    confirmation: Literal["ADD_ACCOUNTS"]
    consent_accepted: bool
    consent_version: str = Field(min_length=1, max_length=64)


class AccountOnboardingCodeRequest(AccountOnboardingMutationRequest):
    code: str = Field(min_length=1, max_length=32)


class AccountOnboardingPasswordRequest(AccountOnboardingMutationRequest):
    password: str = Field(min_length=1, max_length=512)


class AccountOnboardingArtifactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=128)
    source_type: SourceType
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)


class AccountOnboardingCountersRead(BaseModel):
    total_count: int
    valid_count: int
    ready_count: int
    failed_count: int
    blocked_count: int
    requires_reauth_count: int


class AccountOnboardingBatchRead(BaseModel):
    id: str
    source_type: str
    status: str
    label: str | None
    counters: AccountOnboardingCountersRead
    created_at: datetime
    updated_at: datetime
    consent_confirmed_at: datetime | None
    confirmed_at: datetime | None
    queued_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    failure_code: str | None
    failure_message: str | None


class AccountOnboardingItemRead(BaseModel):
    id: str
    batch_id: str
    account_id: str | None
    auth_session_id: str | None
    source_type: str
    position: int
    status: str
    phone_hint: str | None
    username_hint: str | None
    telegram_user_id_hint: str | None
    label: str | None
    validation_code: str | None
    validation_message: str | None
    risk_level: str
    requires_reauth: bool
    last_error_code: str | None
    last_error_message: str | None
    created_at: datetime
    updated_at: datetime
    next_retry_at: datetime | None
    next_action: str | None = None


class AccountOnboardingSnapshotRead(BaseModel):
    batch: AccountOnboardingBatchRead
    items: list[AccountOnboardingItemRead]
    capabilities: list[OnboardingCapabilityRead]
    poll_again_in_ms: int
    next_action: str | None = None


class AccountOnboardingArtifactRead(BaseModel):
    id: str
    source_type: str
    sha256: str
    size_bytes: int
    content_type_detected: str
    status: str
    created_at: datetime
    expires_at: datetime
    failure_code: str | None
    failure_message: str | None
