"""Regression tests for the canonical branch-protection ruleset (issue #272)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / ".github" / "branch-protection.main.json"
TEST_QUALITY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test-quality.yml"

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


def _workflow_job_ids() -> set[str]:
    """Return the set of job ids declared under ``jobs:`` in test-quality.yml.

    A "context" reported to branch protection is ``<workflow name> / <job id|name>``;
    GitHub uses ``name:`` if present, falling back to the job id. We expose both.
    """
    text = TEST_QUALITY_WORKFLOW.read_text(encoding="utf-8")
    in_jobs = False
    ids: set[str] = set()
    names: set[str] = set()
    job_id_re = re.compile(r"^  ([a-zA-Z0-9_-]+):\s*$")
    name_re = re.compile(r"^    name:\s*(.+?)\s*$")
    current_id: str | None = None
    for line in text.splitlines():
        if line.startswith("jobs:"):
            in_jobs = True
            continue
        if not in_jobs:
            continue
        if line and not line.startswith(" "):
            in_jobs = False
            continue
        m = job_id_re.match(line)
        if m:
            current_id = m.group(1)
            ids.add(current_id)
            continue
        m = name_re.match(line)
        if m and current_id is not None:
            names.add(m.group(1))
    return ids | names


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


def test_config_has_no_underscore_prefixed_metadata_keys() -> None:
    """Direct `gh api --input` may reject unknown top-level keys.

    Apply-runbook comments live in ``docs/quality/REQUIRED_CHECKS.md``,
    not in the JSON payload. Any ``_comment`` / ``_note`` field is a
    leak from documentation into the API payload — reject it.
    """
    data = _load()
    leaks = [k for k in data if k.startswith("_")]
    assert not leaks, (
        f"branch-protection JSON must contain only API-recognised keys; "
        f"move metadata to docs/quality/REQUIRED_CHECKS.md. Offenders: {leaks}"
    )


def test_required_contexts_exist_as_workflow_job_names() -> None:
    """Every required context maps to a real job id/name in test-quality.yml.

    Drift between the ruleset and the workflow is silent in CI but breaks
    branch protection — an unknown context name behaves as "permanently
    pending", blocking every PR. Pin both sides here.
    """
    data = _load()
    declared_jobs = _workflow_job_ids()
    contexts = set(data["required_status_checks"]["contexts"])
    missing: list[str] = []
    for ctx in contexts:
        if not ctx.startswith("Test Quality / "):
            continue
        job = ctx.removeprefix("Test Quality / ")
        if job not in declared_jobs:
            missing.append(ctx)
    assert not missing, (
        "branch-protection required contexts reference job names that do not "
        f"exist in test-quality.yml jobs:. Drift: {missing}. "
        f"Declared jobs: {sorted(declared_jobs)}"
    )
