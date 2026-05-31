from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_serializer, field_validator

__all__ = [
    "Any",
    "ApprovalMode",
    "AutoSendDisabled",
    "BaseModel",
    "CampaignMode",
    "ChannelRuleType",
    "ConfigDict",
    "DelayMaxInt",
    "Field",
    "LimitScopeType",
    "LimitType",
    "Literal",
    "NonNegativeInt",
    "PositiveInt",
    "RotationStrategy",
    "SafetyPreset",
    "SendMode",
    "SendStrategy",
    "StrictBool",
    "WorkMode",
    "_DISABLED_CAMPAIGN_MODES",
    "_DISABLED_WORK_MODES",
    "_empty_keywords",
    "_reject_disabled_value",
    "_serialize_utc_datetime",
    "datetime",
    "field_serializer",
    "field_validator",
]

PositiveInt = Annotated[int, Field(ge=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]
DelayMaxInt = Annotated[int, Field(ge=60)]
CampaignMode = Literal["all_posts", "keyword_match", "random_posts", "semantic_match"]
WorkMode = Literal["by_comment_count", "by_time_window", "manual", "scheduled"]
ApprovalMode = Literal["manual_required", "trusted_auto", "auto"]
SendMode = Literal["dry_run", "manual_approval", "semi_auto"]
SendStrategy = Literal["comment"]
RotationStrategy = Literal["round_robin", "weighted", "least_used", "random"]
AutoSendDisabled = Literal[False]
LimitScopeType = Literal[
    "workspace", "campaign", "account", "target", "campaign_account", "campaign_target"
]
LimitType = Literal[
    "comments_per_minute",
    "comments_per_hour",
    "comments_per_day",
    "min_delay_between_comments",
    "max_parallel_attempts",
]
ChannelRuleType = Literal["blacklist", "whitelist"]
SafetyPreset = Literal["conservative", "balanced", "aggressive"]

# Phase 0 Task 1: enum values declared in DB/python enum but not yet implemented.
# Reject at Create/Update boundary with feature_not_available marker.
_DISABLED_CAMPAIGN_MODES: frozenset[str] = frozenset({"semantic_match"})
_DISABLED_WORK_MODES: frozenset[str] = frozenset({"scheduled"})


def _reject_disabled_value(value: object, *, disabled: frozenset[str], feature: str) -> object:
    if isinstance(value, str) and value in disabled:
        raise ValueError(f"feature_not_available: {feature}={value}")
    return value


def _serialize_utc_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat().replace("+00:00", "Z")


def _empty_keywords() -> list[str]:
    return []
