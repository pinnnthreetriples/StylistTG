"""Tests for the canonical pytest profile registry (issue #264)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import enforce_slow_test_budget, pytest_profiles

pytestmark = pytest.mark.unit


REPO_ROOT = Path(__file__).resolve().parents[2]


# ---- Profile registry --------------------------------------------------------


def test_pr_profile_excludes_all_heavy_markers() -> None:
    expr = pytest_profiles.PR.marker_expr
    for marker in (
        "contract",
        "live",
        "integration",
        "postgres",
        "redis",
        "slow",
        "benchmark",
        "mutation",
        "property_heavy",
        "nightly",
    ):
        assert f"not {marker}" in expr, f"PR profile must exclude marker '{marker}'"


def test_pr_profile_does_not_exclude_property_pr() -> None:
    expr = pytest_profiles.PR.marker_expr
    assert "property_pr" not in expr.replace("property_heavy", ""), (
        "PR profile must keep `property_pr` selectable so fast property tests run on PR"
    )


def test_all_profiles_have_unique_names_and_paths() -> None:
    names = [p.name for p in pytest_profiles.ALL_PROFILES.values()]
    assert len(names) == len(set(names)), f"duplicate profile names: {names}"
    for profile in pytest_profiles.ALL_PROFILES.values():
        assert profile.paths, f"profile {profile.name} has empty paths tuple"
        assert profile.marker_expr, f"profile {profile.name} has empty marker_expr"


def test_cli_prints_marker_expression_for_known_profile() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "scripts.pytest_profiles", "pr-markers"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == pytest_profiles.PR.marker_expr


def test_cli_rejects_unknown_profile() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "scripts.pytest_profiles", "bogus-markers"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "invalid choice" in result.stderr or "bogus-markers" in result.stderr


# ---- Slow-test budget enforcement -------------------------------------------


def test_enforce_slow_test_budget_passes_on_empty_report(tmp_path: Path) -> None:
    report = tmp_path / "slow-tests.json"
    report.write_text(json.dumps({"entries": []}), encoding="utf-8")
    # The script resolves the report path relative to REPO_ROOT; pass absolute.
    exit_code = enforce_slow_test_budget.main(
        ["--report", str(report), "--max-call-seconds", "1.0", "--max-setup-seconds", "1.0"]
    )
    assert exit_code == 0


def test_enforce_slow_test_budget_skips_missing_report(tmp_path: Path) -> None:
    exit_code = enforce_slow_test_budget.main(["--report", str(tmp_path / "missing.json")])
    assert exit_code == 0


def test_enforce_slow_test_budget_require_report_fails_when_missing(tmp_path: Path) -> None:
    exit_code = enforce_slow_test_budget.main(
        ["--report", str(tmp_path / "missing.json"), "--require-report"]
    )
    assert exit_code == 2, (
        "--require-report must exit 2 when the report is absent so a broken "
        "report generator cannot silently disable the runtime-budget gate in CI"
    )


def test_enforce_slow_test_budget_require_report_passes_when_present(tmp_path: Path) -> None:
    report = tmp_path / "slow-tests.json"
    report.write_text(json.dumps({"entries": []}), encoding="utf-8")
    exit_code = enforce_slow_test_budget.main(
        ["--report", str(report), "--require-report", "--max-call-seconds", "1.0"]
    )
    assert exit_code == 0


def test_enforce_slow_test_budget_flags_unmarked_violation(tmp_path: Path) -> None:
    report = tmp_path / "slow-tests.json"
    report.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "nodeid": "tests/does_not_exist.py::test_slow",
                        "phase": "call",
                        "seconds": 10.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    exit_code = enforce_slow_test_budget.main(
        ["--report", str(report), "--max-call-seconds", "1.0"]
    )
    assert exit_code == 1


def test_enforce_slow_test_budget_exempts_marked_test(tmp_path: Path) -> None:
    report = tmp_path / "slow-tests.json"
    report.write_text(
        json.dumps(
            {
                "entries": [
                    # Real marked test in the suite — `slow` marker exempts it.
                    {
                        "nodeid": "tests/benchmarks/test_safety_gate_perf.py::test_anything",
                        "phase": "call",
                        "seconds": 30.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    exit_code = enforce_slow_test_budget.main(
        ["--report", str(report), "--max-call-seconds", "1.0"]
    )
    assert exit_code == 0
