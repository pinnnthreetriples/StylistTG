from __future__ import annotations

from pathlib import Path

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
