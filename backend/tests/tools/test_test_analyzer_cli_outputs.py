from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.test_analyzer import main


def test_cli_multi_output_writes_json(tmp_path: Path) -> None:
    test_file = tmp_path / "test_ok.py"
    report_dir = tmp_path / "reports"
    test_file.write_text(
        "def test_fine():\n    assert len([1, 2]) == 2\n", encoding="utf-8"
    )

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

    assert (report_dir / "test-quality.json").is_file()


def test_cli_multi_output_creates_sarif(tmp_path: Path) -> None:
    test_file = tmp_path / "test_ok.py"
    report_dir = tmp_path / "reports"
    test_file.write_text(
        "def test_fine():\n    assert len([1, 2]) == 2\n", encoding="utf-8"
    )

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

    assert (
        json.loads((report_dir / "test-quality.sarif").read_text(encoding="utf-8"))[
            "version"
        ]
        == "2.1.0"
    )


def test_cli_multi_output_rejects_single_output(tmp_path: Path) -> None:
    test_file = tmp_path / "test_ok.py"
    test_file.write_text(
        "def test_fine():\n    assert len([1, 2]) == 2\n", encoding="utf-8"
    )

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
