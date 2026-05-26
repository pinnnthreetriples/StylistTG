from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import coverage_gate


def _write_coverage(tmp_path: Path, files: dict[str, dict[str, int]]) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    payload = {
        "files": {
            path: {
                "summary": {
                    "covered_lines": values["covered_lines"],
                    "num_statements": values["num_statements"],
                    "covered_branches": values["covered_branches"],
                    "num_branches": values["num_branches"],
                }
            }
            for path, values in files.items()
        }
    }
    (reports / "coverage.json").write_text(json.dumps(payload), encoding="utf-8")


def _passing_critical_files() -> dict[str, dict[str, int]]:
    files: dict[str, dict[str, int]] = {}
    for path, _line, _branch in coverage_gate.CRITICAL_FILE_THRESHOLDS:
        files[path] = {
            "covered_lines": 100,
            "num_statements": 100,
            "covered_branches": 100,
            "num_branches": 100,
        }
    return files


def test_coverage_gate_fails_when_critical_file_branch_coverage_regresses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = _passing_critical_files()
    files["app/services/secret_redaction.py"] = {
        "covered_lines": 29,
        "num_statements": 29,
        "covered_branches": 7,
        "num_branches": 8,
    }
    _write_coverage(
        tmp_path,
        files
        | {
            "app/services/other.py": {
                "covered_lines": 400,
                "num_statements": 400,
                "covered_branches": 400,
                "num_branches": 400,
            },
        },
    )
    monkeypatch.chdir(tmp_path)

    assert coverage_gate.main() == 1


def test_coverage_gate_passes_when_critical_file_thresholds_are_met(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_coverage(
        tmp_path,
        _passing_critical_files()
        | {
            "app/services/other.py": {
                "covered_lines": 400,
                "num_statements": 400,
                "covered_branches": 400,
                "num_branches": 400,
            },
        },
    )
    monkeypatch.chdir(tmp_path)

    assert coverage_gate.main() == 0


def test_critical_file_threshold_paths_exist() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    missing = [
        path
        for path, _line, _branch in coverage_gate.CRITICAL_FILE_THRESHOLDS
        if not (backend_root / path).exists()
    ]

    assert missing == []
