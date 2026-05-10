from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicyDecision:
    retry: bool
    max_attempts: int
    interval_seconds: list[int]
    failure_ttl_seconds: int = 604800
    result_ttl_seconds: int = 86400
    error_category: str = "unknown_transient"

    def to_dict(self) -> dict[str, object]:
        return {
            "retry": self.retry,
            "max_attempts": self.max_attempts,
            "interval_seconds": self.interval_seconds,
            "failure_ttl_seconds": self.failure_ttl_seconds,
            "result_ttl_seconds": self.result_ttl_seconds,
            "error_category": self.error_category,
        }


NO_RETRY_CATEGORIES = {"auth_required", "validation_error", "blocked_by_risk", "account_locked", "unknown_permanent"}


def classify_error_category(error_code: str | None, error_class: str | None = None) -> str:
    token = f"{error_code or ''} {error_class or ''}".lower()
    if "flood_wait" in token or "floodwait" in token:
        return "flood_wait"
    if "auth" in token or "reauth" in token:
        return "auth_required"
    if "proxy" in token:
        return "proxy_failed"
    if "tdlib" in token or "timeout" in token:
        return "tdlib_unavailable"
    if "validation" in token or "invalid" in token:
        return "validation_error"
    if "rate" in token:
        return "rate_limited"
    if "lock" in token:
        return "account_locked"
    return "unknown_transient"


def retry_policy_for(error_category: str, *, job_type: str = "profile_update", attempt: int = 1) -> RetryPolicyDecision:
    if error_category == "flood_wait":
        return RetryPolicyDecision(retry=False, max_attempts=1, interval_seconds=[], error_category=error_category)
    if error_category in NO_RETRY_CATEGORIES:
        return RetryPolicyDecision(retry=False, max_attempts=1, interval_seconds=[], error_category=error_category)
    if error_category == "proxy_failed":
        return RetryPolicyDecision(retry=attempt < 3, max_attempts=3, interval_seconds=[60, 300], error_category=error_category)
    if error_category == "tdlib_unavailable":
        return RetryPolicyDecision(retry=attempt < 4, max_attempts=4, interval_seconds=[30, 120, 300], error_category=error_category)
    if error_category == "rate_limited":
        return RetryPolicyDecision(retry=attempt < 2, max_attempts=2, interval_seconds=[3600], error_category=error_category)
    return RetryPolicyDecision(retry=attempt < 3, max_attempts=3, interval_seconds=[30, 120], error_category=error_category)
