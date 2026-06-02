"""Regression: every contract-security exclusion is well-formed (issue #266)."""

from __future__ import annotations

import pytest

from tests.contract.security.exclusions import (
    CONTRACT_SECURITY_EXCLUSIONS,
    ContractExclusion,
)

pytestmark = pytest.mark.unit


def test_every_exclusion_has_owner_and_follow_up() -> None:
    for exclusion in CONTRACT_SECURITY_EXCLUSIONS:
        assert exclusion.owner.startswith("@"), (
            f"exclusion for {exclusion.path_pattern} {exclusion.method} must have a GitHub handle owner"
        )
        assert exclusion.follow_up_issue.startswith("#"), (
            f"exclusion for {exclusion.path_pattern} {exclusion.method} must reference a tracking issue"
        )


def test_exclusion_rejects_relative_path() -> None:
    with pytest.raises(ValueError, match="must start with '/'"):
        ContractExclusion(
            path_pattern="api/relative",
            method="GET",
            reason="…",
            owner="@octocat",
            follow_up_issue="#1",
        )


def test_exclusion_rejects_unknown_method() -> None:
    with pytest.raises(ValueError, match="must be an HTTP verb"):
        ContractExclusion(
            path_pattern="/api/x",
            method="CONNECT",
            reason="…",
            owner="@octocat",
            follow_up_issue="#1",
        )


def test_exclusion_rejects_blank_reason() -> None:
    with pytest.raises(ValueError, match="requires a non-empty reason"):
        ContractExclusion(
            path_pattern="/api/x",
            method="GET",
            reason="   ",
            owner="@octocat",
            follow_up_issue="#1",
        )


def test_exclusion_rejects_missing_owner_prefix() -> None:
    with pytest.raises(ValueError, match="GitHub handle"):
        ContractExclusion(
            path_pattern="/api/x",
            method="GET",
            reason="reason",
            owner="octocat",
            follow_up_issue="#1",
        )


def test_exclusion_rejects_missing_issue_link() -> None:
    with pytest.raises(ValueError, match="reference an issue"):
        ContractExclusion(
            path_pattern="/api/x",
            method="GET",
            reason="reason",
            owner="@octocat",
            follow_up_issue="see-jira",
        )


def test_exclusion_accepts_well_formed_entry() -> None:
    exclusion = ContractExclusion(
        path_pattern="/api/example",
        method="GET",
        reason="endpoint is behind feature flag",
        owner="@octocat",
        follow_up_issue="#42",
    )
    assert exclusion.path_pattern == "/api/example"
    assert exclusion.owner == "@octocat"
    assert exclusion.follow_up_issue == "#42"
