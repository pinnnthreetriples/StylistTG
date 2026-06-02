"""Regression tests for the canonical branch-protection ruleset (issue #272)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / ".github" / "branch-protection.main.json"

REQUIRED_CONTEXTS = {
    "Test Quality / test-quality-pr",
    "Test Quality / lint-format",
    "Test Quality / typecheck",
    "Test Quality / backend-tests",
    "Test Quality / audit",
    "Test Quality / duplication",
    "Test Quality / contract-security",
}


def _load() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def test_config_file_exists() -> None:
    assert CONFIG_PATH.is_file(), f"missing {CONFIG_PATH}"


def test_required_status_checks_strict_mode_enabled() -> None:
    data = _load()
    assert data["required_status_checks"]["strict"] is True


def test_required_status_checks_include_test_quality_aggregator() -> None:
    data = _load()
    contexts = set(data["required_status_checks"]["contexts"])
    missing = REQUIRED_CONTEXTS - contexts
    assert not missing, f"required contexts missing from ruleset: {sorted(missing)}"


def test_admins_cannot_bypass() -> None:
    data = _load()
    assert data["enforce_admins"] is True


def test_force_push_and_deletion_are_disabled() -> None:
    data = _load()
    assert data["allow_force_pushes"] is False
    assert data["allow_deletions"] is False


def test_linear_history_and_conversation_resolution_required() -> None:
    data = _load()
    assert data["required_linear_history"] is True
    assert data["required_conversation_resolution"] is True


def test_pr_reviews_require_at_least_one_approval() -> None:
    data = _load()
    reviews = data["required_pull_request_reviews"]
    assert reviews["required_approving_review_count"] >= 1
    assert reviews["dismiss_stale_reviews"] is True
