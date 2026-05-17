from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.contracts.accounts import ProfileAudioAction, ProfilePreviewRead
from app.contracts.jobs import JobSummaryRead
from app.contracts.safety import (
    AccountOperationCooldownRead,
    AccountOperationSafetyRead,
    AccountRiskRead,
    AccountSafetyRead,
)


def _empty_update_stories() -> list[AccountUpdateStoryDesiredState]:
    return []


def _empty_operation_safety_items() -> list[AccountOperationSafetyRead]:
    return []


class AccountUpdateProfileDesiredState(BaseModel):
    name: str | None = None
    bio: str | None = None
    username: str | None = None
    photo_asset_id: str | None = None


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
    account_id: str
    profile: AccountUpdateProfileDesiredState | None = None
    profile_audio: AccountUpdateProfileAudioDesiredState | None = None
    stories: list[AccountUpdateStoryDesiredState] = Field(default_factory=_empty_update_stories)


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


__all__ = [
    "AccountUpdateCreate",
    "AccountUpdateJobSummaryRead",
    "AccountUpdatePreviewRead",
    "AccountUpdateProfileAudioDesiredState",
    "AccountUpdateProfileDesiredState",
    "AccountUpdateStoryDesiredState",
]
