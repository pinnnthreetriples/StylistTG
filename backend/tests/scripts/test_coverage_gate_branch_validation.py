"""Tests for the branch-aware coverage gate (issue #265)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import coverage_gate

pytestmark = pytest.mark.unit


def _write_coverage_json(path: Path, *, branch_coverage: bool, files: dict[str, Any]) -> None:
    payload = {
        "meta": {
            "format": 3,
            "version": "7.0",
            "timestamp": "2026-06-02T01:00:00Z",
            "branch_coverage": branch_coverage,
            "show_contexts": False,
        },
        "files": files,
        "totals": {},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _file_summary(*, lines: int, covered_lines: int, branches: int, covered_branches: int) -> dict:
    return {
        "summary": {
            "num_statements": lines,
            "covered_lines": covered_lines,
            "num_branches": branches,
            "covered_branches": covered_branches,
        }
    }


# ---- Branch-data validation -------------------------------------------------


def test_main_fails_when_branch_coverage_disabled(tmp_path: Path) -> None:
    report = tmp_path / "coverage.json"
    _write_coverage_json(report, branch_coverage=False, files={})
    assert coverage_gate.main(report) == 2


def test_main_fails_when_meta_missing(tmp_path: Path) -> None:
    report = tmp_path / "coverage.json"
    report.write_text(json.dumps({"files": {}, "totals": {}}), encoding="utf-8")
    assert coverage_gate.main(report) == 2


def test_main_fails_when_report_missing(tmp_path: Path) -> None:
    assert coverage_gate.main(tmp_path / "absent.json") == 2


def test_validate_branch_data_accepts_strict_report() -> None:
    assert (
        coverage_gate._validate_branch_data(
            {"meta": {"branch_coverage": True}, "files": {}, "totals": {}}
        )
        is None
    )


# ---- Critical file gates -----------------------------------------------------


def test_critical_file_missing_from_report_fails(tmp_path: Path) -> None:
    report = tmp_path / "coverage.json"
    # Include packages but omit the critical files — gate should still fail.
    _write_coverage_json(
        report,
        branch_coverage=True,
        files={
            "app/api/foo.py": _file_summary(
                lines=100, covered_lines=100, branches=10, covered_branches=10
            ),
        },
    )
    assert coverage_gate.main(report) == 1


def test_critical_file_below_branch_floor_fails(tmp_path: Path) -> None:
    report = tmp_path / "coverage.json"
    # Build a file set with every CRITICAL_FILE_THRESHOLDS entry present at
    # 100% line / 100% branch except secret_redaction.py which gets 50% branch.
    files: dict[str, Any] = {}
    for crit_path, _line, _branch in coverage_gate.CRITICAL_FILE_THRESHOLDS:
        if crit_path == "app/services/secret_redaction.py":
            files[crit_path] = _file_summary(
                lines=10, covered_lines=10, branches=10, covered_branches=5
            )
        else:
            files[crit_path] = _file_summary(
                lines=10, covered_lines=10, branches=10, covered_branches=10
            )
    # Also stub all package buckets so per-package check passes.
    for pkg, _line, _branch in coverage_gate.THRESHOLDS:
        files[f"{pkg}/_stub.py"] = _file_summary(
            lines=100, covered_lines=100, branches=10, covered_branches=10
        )
    _write_coverage_json(report, branch_coverage=True, files=files)
    assert coverage_gate.main(report) == 1


# ---- Threshold helpers -------------------------------------------------------


def test_branch_pct_zero_branches_means_full() -> None:
    assert coverage_gate._branch_pct({"num_branches": 0, "covered_branches": 0}) == 100.0


def test_line_pct_partial() -> None:
    assert coverage_gate._line_pct({"num_statements": 4, "covered_lines": 3}) == 75.0


def test_pkg_for_assigns_prefix() -> None:
    expected = coverage_gate.THRESHOLDS[0][0]
    assert coverage_gate._pkg_for(f"{expected}/sub/module.py") == expected


def test_pkg_for_returns_none_for_unrelated_path() -> None:
    assert coverage_gate._pkg_for("docs/not_a_package.py") is None
