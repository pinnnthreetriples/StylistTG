from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.test_analyzer import main


def _write_ok_test(path: Path) -> None:
    path.write_text("def test_fine():\n    assert len([1, 2]) == 2\n", encoding="utf-8")


def _run_multi_output(tmp_path: Path) -> Path:
    test_file = tmp_path / "test_ok.py"
    report_dir = tmp_path / "reports"
    _write_ok_test(test_file)

    main(
        [
            "--path",
            str(test_file),
            "--format",
            "json,sarif",
            "--output-dir",
            str(report_dir),
        ]
    )
    return report_dir


def test_cli_multi_output_writes_json(tmp_path: Path) -> None:
    report_dir = _run_multi_output(tmp_path)

    assert (report_dir / "test-quality.json").is_file()


def test_cli_multi_output_creates_sarif(tmp_path: Path) -> None:
    report_dir = _run_multi_output(tmp_path)

    assert (
        json.loads((report_dir / "test-quality.sarif").read_text(encoding="utf-8"))["version"]
        == "2.1.0"
    )


def test_cli_multi_output_rejects_single_output(tmp_path: Path) -> None:
    test_file = tmp_path / "test_ok.py"
    _write_ok_test(test_file)

    with pytest.raises(SystemExit):
        main(
            [
                "--path",
                str(test_file),
                "--format",
                "json,sarif",
                "--output",
                str(tmp_path / "report.json"),
            ]
        )
