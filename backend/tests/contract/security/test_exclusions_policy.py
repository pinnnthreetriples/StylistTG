"""Regression: every contract-security exclusion is well-formed (issue #266)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests.contract.security.exclusions import (
    CONTRACT_SECURITY_EXCLUSIONS,
    MAX_EXCLUSION_DAYS,
    ContractExclusion,
)

pytestmark = pytest.mark.unit


def _valid_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "path_pattern": "/api/example",
        "method": "GET",
        "reason": "endpoint is behind feature flag",
        "owner": "@octocat",
        "follow_up_issue": "#42",
        "expires_at": (date.today() + timedelta(days=30)).isoformat(),
    }
    base.update(overrides)
    return base


def test_every_exclusion_has_owner_follow_up_and_expiry() -> None:
    today = date.today()
    for exclusion in CONTRACT_SECURITY_EXCLUSIONS:
        assert exclusion.owner.startswith("@"), (
            f"exclusion for {exclusion.path_pattern} {exclusion.method} must have a GitHub handle owner"
        )
        assert exclusion.follow_up_issue.startswith("#"), (
            f"exclusion for {exclusion.path_pattern} {exclusion.method} must reference a tracking issue"
        )
        assert not exclusion.is_expired(today=today), (
            f"contract-security exclusion {exclusion.path_pattern} {exclusion.method} "
            f"expired on {exclusion.expires_at} — either remove it or extend with "
            f"a renewed justification (cap: {MAX_EXCLUSION_DAYS} days)."
        )


def test_exclusion_rejects_relative_path() -> None:
    with pytest.raises(ValueError, match="must start with '/'"):
        ContractExclusion(**_valid_kwargs(path_pattern="api/relative"))


def test_exclusion_rejects_unknown_method() -> None:
    with pytest.raises(ValueError, match="must be an HTTP verb"):
        ContractExclusion(**_valid_kwargs(method="CONNECT"))


def test_exclusion_rejects_blank_reason() -> None:
    with pytest.raises(ValueError, match="requires a non-empty reason"):
        ContractExclusion(**_valid_kwargs(reason="   "))


def test_exclusion_rejects_missing_owner_prefix() -> None:
    with pytest.raises(ValueError, match="GitHub handle"):
        ContractExclusion(**_valid_kwargs(owner="octocat"))


def test_exclusion_rejects_missing_issue_link() -> None:
    with pytest.raises(ValueError, match="reference an issue"):
        ContractExclusion(**_valid_kwargs(follow_up_issue="see-jira"))


def test_exclusion_rejects_missing_expires_at() -> None:
    # expires_at is mandatory: omit via the dataclass-level TypeError path.
    with pytest.raises(TypeError, match="expires_at"):
        ContractExclusion(  # type: ignore[call-arg]
            path_pattern="/api/example",
            method="GET",
            reason="reason",
            owner="@octocat",
            follow_up_issue="#42",
        )


def test_exclusion_rejects_malformed_expires_at() -> None:
    with pytest.raises(ValueError, match="must be ISO YYYY-MM-DD"):
        ContractExclusion(**_valid_kwargs(expires_at="2026/06/30"))


def test_exclusion_is_expired_after_expiry_date() -> None:
    yesterday = date.today() - timedelta(days=1)
    exclusion = ContractExclusion(**_valid_kwargs(expires_at=yesterday.isoformat()))
    assert exclusion.is_expired() is True


def test_exclusion_is_not_expired_on_expiry_date() -> None:
    today = date.today()
    exclusion = ContractExclusion(**_valid_kwargs(expires_at=today.isoformat()))
    assert exclusion.is_expired() is False


def test_exclusion_accepts_well_formed_entry() -> None:
    exclusion = ContractExclusion(**_valid_kwargs())
    assert exclusion.path_pattern == "/api/example"
    assert exclusion.owner == "@octocat"
    assert exclusion.follow_up_issue == "#42"
    assert not exclusion.is_expired()
