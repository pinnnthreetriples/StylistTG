from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.contracts.jobs import JobSummaryRead
from app.modules.account_core.contracts import ProfileAudioAction, ProfilePreviewRead
from app.modules.account_safety.contracts import (
    AccountOperationCooldownRead,
    AccountOperationSafetyRead,
    AccountRiskRead,
    AccountSafetyRead,
)
from app.contracts.types import UuidString


def _empty_update_stories() -> list[AccountUpdateStoryDesiredState]:
    return []


def _empty_operation_safety_items() -> list[AccountOperationSafetyRead]:
    return []


class AccountUpdateProfileDesiredState(BaseModel):
    name: str | None = None
    bio: str | None = None
    username: str | None = None
    photo_asset_id: str | None = None
    pinned_channel_ref: str | None = None


class AccountUpdateProfileAudioDesiredState(BaseModel):
    action: ProfileAudioAction = ProfileAudioAction.KEEP
    audio_asset_id: str | None = None


class AccountUpdateStoryDesiredState(BaseModel):
    action: Literal["post_image", "post_video"]
    asset_id: str
    caption: str | None = None
    privacy_preset: str = "contacts"
    active_period_seconds: int = 86400
    protect_content: bool = False


class AccountUpdateCreate(BaseModel):
    account_id: UuidString
    profile: AccountUpdateProfileDesiredState | None = None
    profile_audio: AccountUpdateProfileAudioDesiredState | None = None
    stories: list[AccountUpdateStoryDesiredState] = Field(default_factory=_empty_update_stories)
    force_profile_uniqueness: bool = False


class AccountProfileUniquenessMatchRead(BaseModel):
    account_id: UuidString
    score: float
    reasons: list[str] = Field(default_factory=list)


class AccountProfileUniquenessRead(BaseModel):
    severity: Literal["ok", "warning", "blocked"]
    similar_count: int
    blocking_count: int
    max_score: float
    matches: list[AccountProfileUniquenessMatchRead] = Field(
        default_factory=list[AccountProfileUniquenessMatchRead]
    )


class AIProfileGenerateBioRequest(BaseModel):
    language: str = "ru"
    persona_hints: dict[str, str] = Field(default_factory=dict)


class AIProfileGenerateAvatarRequest(BaseModel):
    persona_hints: dict[str, str] = Field(default_factory=dict)


class AIProfileGenerateBioRead(BaseModel):
    bio: str
    provider: str
    model: str
    attempts: int
    uniqueness: AccountProfileUniquenessRead


class AIProfileGenerateAvatarRead(BaseModel):
    asset_id: UuidString
    provider: str
    model: str
    mime: str
    attempts: int
    uniqueness: AccountProfileUniquenessRead


class AccountUpdateJobSummaryRead(JobSummaryRead):
    workflow_type: str
    workflow_version: int


class AccountUpdatePreviewRead(ProfilePreviewRead):
    workflow_type: str
    workflow_version: int
    desired_state_normalized: dict[str, Any]
    capability_snapshot: dict[str, str]
    account_safety: AccountSafetyRead | None = None
    risk_by_operation: dict[str, AccountRiskRead] = Field(default_factory=dict)
    cooldowns_by_operation: dict[str, list[AccountOperationCooldownRead]] = Field(
        default_factory=dict
    )
    safety_warnings: list[str] = Field(default_factory=list)
    safety_blockers: list[str] = Field(default_factory=list)
    operation_safety: list[AccountOperationSafetyRead] = Field(
        default_factory=_empty_operation_safety_items
    )
    profile_uniqueness: AccountProfileUniquenessRead | None = None


__all__ = [
    "AIProfileGenerateAvatarRead",
    "AIProfileGenerateAvatarRequest",
    "AIProfileGenerateBioRead",
    "AIProfileGenerateBioRequest",
    "AccountProfileUniquenessMatchRead",
    "AccountProfileUniquenessRead",
    "AccountUpdateCreate",
    "AccountUpdateJobSummaryRead",
    "AccountUpdatePreviewRead",
    "AccountUpdateProfileAudioDesiredState",
    "AccountUpdateProfileDesiredState",
    "AccountUpdateStoryDesiredState",
]
