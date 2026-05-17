"""Run pytest with reruns and emit a JSON report for flaky candidates."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
RERUN_RE = re.compile(r"\bRERUN\b\s+([^\s]+::[^\s]+)")


def _candidate_ids(output: str) -> list[str]:
    candidates: set[str] = set()
    for line in output.splitlines():
        match = RERUN_RE.search(line)
        if match:
            candidates.add(match.group(1))
    return sorted(candidates)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--reruns", default="2")
    parser.add_argument("--reruns-delay", default="1")
    parser.add_argument("--marker", default="not live and not contract")
    args = parser.parse_args()

    reports_dir = (REPO_ROOT / args.reports_dir).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)
    junit_path = reports_dir / "flaky-junit.xml"
    log_path = reports_dir / "flaky-pytest.log"
    report_path = reports_dir / "flaky-report.json"

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-n",
        "auto",
        "--dist=loadscope",
        "-m",
        args.marker,
        "--reruns",
        args.reruns,
        "--reruns-delay",
        args.reruns_delay,
        f"--junitxml={junit_path.as_posix()}",
        "-ra",
    ]

    print(" ".join(shlex.quote(part) for part in cmd), flush=True)
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.stdout:
        print(result.stdout, end="")
    log_path.write_text(result.stdout or "", encoding="utf-8")

    candidates = _candidate_ids(result.stdout or "")
    report: dict[str, Any] = {
        "returncode": result.returncode,
        "reruns": int(args.reruns),
        "flaky_candidates": candidates,
        "candidate_count": len(candidates),
        "junit": junit_path.as_posix(),
        "log": log_path.as_posix(),
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if candidates:
        print("Flaky candidates detected:")
        for candidate in candidates:
            print(f"- {candidate}")
        print(
            f"::warning title=Flaky candidates detected::{len(candidates)} tests passed only after rerun"
        )
    else:
        print("No flaky candidates detected by rerun profile.")

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
