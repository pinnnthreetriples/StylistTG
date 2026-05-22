from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scripts import flaky_detection


def test_candidate_ids_include_junit_flaky_failures(tmp_path: Path) -> None:
    junit = tmp_path / "flaky-junit.xml"
    junit.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuite>
  <testcase classname="tests.auth.test_login" name="test_retries_once">
    <flakyFailure message="rerun 1">first attempt failed</flakyFailure>
  </testcase>
</testsuite>
""",
        encoding="utf-8",
    )

    assert flaky_detection._candidate_ids("", junit) == ["tests.auth.test_login::test_retries_once"]


def test_main_ignores_contract_tests_in_whole_tree_command(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **_: object) -> SimpleNamespace:
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(flaky_detection.subprocess, "run", fake_run)
    monkeypatch.setattr(
        flaky_detection.sys,
        "argv",
        ["flaky_detection.py", "--reports-dir", str(tmp_path)],
    )

    flaky_detection.main()

    assert "--ignore=tests/contract" in captured["cmd"]
