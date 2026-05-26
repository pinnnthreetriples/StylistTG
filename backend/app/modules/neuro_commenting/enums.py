from __future__ import annotations

from enum import StrEnum


class NeuroCampaignStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class NeuroCampaignMode(StrEnum):
    ALL_POSTS = "all_posts"
    KEYWORD_MATCH = "keyword_match"
    RANDOM_POSTS = "random_posts"
    SEMANTIC_MATCH = "semantic_match"


class NeuroWorkMode(StrEnum):
    BY_COMMENT_COUNT = "by_comment_count"
    BY_TIME_WINDOW = "by_time_window"
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class NeuroApprovalMode(StrEnum):
    MANUAL_REQUIRED = "manual_required"
    TRUSTED_AUTO = "trusted_auto"
    AUTO = "auto"


class NeuroSendMode(StrEnum):
    DRY_RUN = "dry_run"
    MANUAL_APPROVAL = "manual_approval"
    SEMI_AUTO = "semi_auto"
    AUTO = "auto"


class NeuroSendStrategy(StrEnum):
    COMMENT = "comment"
    COMMENT_AS_CHANNEL = "comment_as_channel"
    EMOJI_THEN_EDIT = "emoji_then_edit"


class NeuroRotationStrategy(StrEnum):
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LEAST_USED = "least_used"
    RANDOM = "random"


class NeuroTargetStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    NO_DISCUSSION = "no_discussion"
    BLACKLISTED = "blacklisted"
    FAILED = "failed"
    ARCHIVED = "archived"


class NeuroGeneratedApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"
    EXPIRED = "expired"


class NeuroAttemptStatus(StrEnum):
    CREATED = "created"
    RESERVED = "reserved"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    FLOOD_WAIT = "flood_wait"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class NeuroSafetyStatus(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"
    NEEDS_REVIEW = "needs_review"


class NeuroEventLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class NeuroCampaignAccountStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COOLDOWN = "cooldown"
    FAILED = "failed"
    ARCHIVED = "archived"


class NeuroObservedPostStatus(StrEnum):
    SEEN = "seen"
    PROCESSING = "processing"
    GENERATED = "generated"
    SKIPPED = "skipped"
    FAILED = "failed"


__all__ = [
    "NeuroApprovalMode",
    "NeuroAttemptStatus",
    "NeuroCampaignAccountStatus",
    "NeuroCampaignMode",
    "NeuroCampaignStatus",
    "NeuroEventLevel",
    "NeuroGeneratedApprovalStatus",
    "NeuroObservedPostStatus",
    "NeuroRotationStrategy",
    "NeuroSafetyStatus",
    "NeuroSendMode",
    "NeuroSendStrategy",
    "NeuroTargetStatus",
    "NeuroWorkMode",
]
