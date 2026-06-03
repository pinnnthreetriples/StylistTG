from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contracts.types import UuidString

SourceType = Literal[
    "phone",
    "phone_bulk",
    "json_metadata",
    "tdlib_directory",
    "tdata_archive",
    "session_file",
    "reauth",
]
CreatableSourceType = Literal[
    "phone",
    "phone_bulk",
    "json_metadata",
    "tdlib_directory",
    "tdata_archive",
    "session_file",
]
BASE64_PATTERN = r"^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$"
MAX_METADATA_JSON_ITEMS = 500
MAX_METADATA_JSON_BYTES = 256 * 1024


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

    @field_validator("position", mode="before")
    @classmethod
    def _reject_bool_position(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("position must be an integer")
        return value


def _empty_phone_items() -> list[PhoneOnboardingInput]:
    return []


class AccountOnboardingBatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=128)
    source_type: CreatableSourceType
    label: str | None = Field(default=None, max_length=255)
    phone_items: list[PhoneOnboardingInput] = Field(default_factory=_empty_phone_items)
    metadata_json: Any | None = None
    artifact_id: UuidString | None = None
    filename: str | None = None

    @field_validator("phone_items")
    @classmethod
    def _limit_phone_items(cls, value: list[PhoneOnboardingInput]) -> list[PhoneOnboardingInput]:
        if len(value) > 500:
            raise ValueError("maximum 500 phone items")
        return value

    @field_validator("metadata_json")
    @classmethod
    def _limit_metadata_json(cls, value: Any | None) -> Any | None:
        if value is None:
            return None
        if isinstance(value, list):
            metadata_items = cast(list[Any], value)
            if len(metadata_items) > MAX_METADATA_JSON_ITEMS:
                raise ValueError("maximum 500 metadata items")
        size = len(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        )
        if size > MAX_METADATA_JSON_BYTES:
            raise ValueError("metadata_json is too large")
        return cast(Any | None, value)


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
    source_type: CreatableSourceType
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=4, pattern=BASE64_PATTERN)


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
