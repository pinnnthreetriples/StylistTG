from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.report_slow_tests import (
    SlowTestEntry,
    build_report,
    main,
    parse_pytest_durations,
)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (
            "1.23s call     tests/test_example.py::test_call",
            SlowTestEntry(
                nodeid="tests/test_example.py::test_call",
                phase="call",
                duration_seconds=1.23,
            ),
        ),
        (
            "0.55s setup    tests/test_example.py::test_setup",
            SlowTestEntry(
                nodeid="tests/test_example.py::test_setup",
                phase="setup",
                duration_seconds=0.55,
            ),
        ),
        (
            "10.01s teardown tests/test_example.py::test_teardown",
            SlowTestEntry(
                nodeid="tests/test_example.py::test_teardown",
                phase="teardown",
                duration_seconds=10.01,
            ),
        ),
    ],
)
def test_parse_pytest_durations_extracts_entry(
    line: str,
    expected: SlowTestEntry,
) -> None:
    assert parse_pytest_durations(line) == [expected]


def test_parse_pytest_durations_sorts_slowest_first() -> None:
    log_text = "\n".join(
        [
            "1.00s call tests/test_example.py::test_fast",
            "4.00s call tests/test_example.py::test_slow",
        ]
    )

    assert parse_pytest_durations(log_text)[0].nodeid == "tests/test_example.py::test_slow"


def test_build_report_counts_thresholds() -> None:
    report = build_report(
        [
            SlowTestEntry("tests/test_example.py::test_fast", "call", 2.0),
            SlowTestEntry("tests/test_example.py::test_slow", "call", 6.0),
        ],
        (3.0, 5.0, 10.0),
    )

    assert report["summary"]["over_threshold"] == {"3.0": 1, "5.0": 1, "10.0": 0}


def test_main_writes_json_report(tmp_path: Path) -> None:
    log_path = tmp_path / "pytest.log"
    output_path = tmp_path / "slow-tests.json"
    log_path.write_text("4.25s call tests/test_example.py::test_slow\n", encoding="utf-8")

    main(["--log", str(log_path), "--output", str(output_path), "--threshold", "3"])

    assert json.loads(output_path.read_text(encoding="utf-8"))["summary"]["reported_tests"] == 1
