"""Tests for the quality dashboard / trend snapshot script (issue #275)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import quality_dashboard

pytestmark = pytest.mark.unit


def _write(path: Path, payload: dict | list) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_snapshot_handles_missing_reports(tmp_path: Path) -> None:
    snapshot = quality_dashboard.build_snapshot(tmp_path)
    assert snapshot["schema_version"] == 1
    assert snapshot["coverage"]["available"] is False
    assert snapshot["analyzer"]["available"] is False


def test_build_snapshot_extracts_coverage_totals(tmp_path: Path) -> None:
    _write(
        tmp_path / "coverage.json",
        {
            "meta": {"branch_coverage": True},
            "totals": {
                "percent_covered": 88.5,
                "num_statements": 1000,
                "missing_lines": 115,
                "num_branches": 300,
                "missing_branches": 50,
            },
        },
    )
    snapshot = quality_dashboard.build_snapshot(tmp_path)
    cov = snapshot["coverage"]
    assert cov["available"] is True
    assert cov["branch_coverage"] is True
    assert cov["percent_covered"] == 88.5
    assert cov["missing_branches"] == 50


def test_build_snapshot_extracts_analyzer_severity_counts(tmp_path: Path) -> None:
    _write(
        tmp_path / "test-quality.json",
        {
            "issues": [
                {"rule_id": "TQA001", "severity": "INFO"},
                {"rule_id": "TQA002", "severity": "WARNING"},
                {"rule_id": "TQA002", "severity": "WARNING"},
            ]
        },
    )
    analyzer = quality_dashboard.build_snapshot(tmp_path)["analyzer"]
    assert analyzer["total"] == 3
    assert analyzer["by_severity"]["WARNING"] == 2
    assert analyzer["by_rule"]["TQA002"] == 2


def test_build_snapshot_extracts_slow_tests(tmp_path: Path) -> None:
    _write(
        tmp_path / "slow-tests.json",
        {
            "entries": [
                {"nodeid": "tests/test_a.py::t", "phase": "call", "seconds": 4.5},
                {"nodeid": "tests/test_b.py::t", "phase": "setup", "seconds": 1.2},
            ]
        },
    )
    slow = quality_dashboard.build_snapshot(tmp_path)["slow_tests"]
    assert slow["available"] is True
    assert slow["total"] == 2
    assert slow["max_call_seconds"] == 4.5


def test_build_snapshot_extracts_mutation(tmp_path: Path) -> None:
    _write(
        tmp_path / "mutation-report.json",
        {"score": 82.5, "killed": 200, "survived": 5, "timeout": 2, "incompetent": 1},
    )
    mutation = quality_dashboard.build_snapshot(tmp_path)["mutation"]
    assert mutation["available"] is True
    assert mutation["score"] == 82.5
    assert mutation["survived"] == 5


def test_render_markdown_includes_coverage_when_available() -> None:
    snapshot = {
        "generated_at": "2026-06-02T00:00:00+00:00",
        "git_sha": "abc12345",
        "coverage": {
            "available": True,
            "branch_coverage": True,
            "percent_covered": 90.0,
            "num_statements": 100,
            "missing_lines": 10,
            "num_branches": 20,
            "missing_branches": 2,
        },
        "analyzer": {"available": False, "by_severity": {}, "by_rule": {}, "total": 0},
        "slow_tests": {"available": False},
        "mutation": {"available": False},
    }
    md = quality_dashboard.render_markdown(snapshot)
    assert "StylistTG quality snapshot" in md
    assert "90.0%" in md
    assert "abc12345" in md


def test_main_writes_both_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "snapshot.json"
    out_md = tmp_path / "summary.md"
    code = quality_dashboard.main(
        [
            "--reports-dir",
            str(tmp_path),
            "--output-json",
            str(out_json),
            "--output-md",
            str(out_md),
        ]
    )
    assert code == 0
    assert out_json.is_file()
    assert out_md.is_file()
    payload = json.loads(out_json.read_text())
    assert payload["schema_version"] == 1
