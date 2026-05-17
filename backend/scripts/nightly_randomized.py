"""Run backend pytest repeatedly with fixed pytest-randomly seeds."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEEDS = ("101", "202", "303")


def _run_seed(
    seed: str, reports_dir: Path, marker: str, extra_pytest_args: list[str]
) -> dict[str, Any]:
    junit_path = reports_dir / f"pytest-seed-{seed}.xml"
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-n",
        "auto",
        "--dist=loadscope",
        "-m",
        marker,
        f"--randomly-seed={seed}",
        f"--junitxml={junit_path.as_posix()}",
        *extra_pytest_args,
    ]

    print(f"\n=== randomized seed {seed}", flush=True)
    print(" ".join(shlex.quote(part) for part in cmd), flush=True)
    started_at = time.monotonic()
    result = subprocess.run(cmd, cwd=REPO_ROOT, check=False)
    elapsed_seconds = round(time.monotonic() - started_at, 3)
    status = "passed" if result.returncode == 0 else "failed"
    print(f"seed {seed}: {status} in {elapsed_seconds}s", flush=True)
    return {
        "seed": seed,
        "status": status,
        "returncode": result.returncode,
        "duration_seconds": elapsed_seconds,
        "junit": junit_path.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--seeds", nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--marker", default="not live and not contract")
    parser.add_argument(
        "--pytest-arg",
        action="append",
        default=[],
        help="extra argument forwarded to each pytest invocation; repeat for multiple args",
    )
    args = parser.parse_args()

    reports_dir = (REPO_ROOT / args.reports_dir).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    results = [
        _run_seed(str(seed), reports_dir, args.marker, args.pytest_arg) for seed in args.seeds
    ]
    summary = {
        "seeds": [result["seed"] for result in results],
        "results": results,
        "failed_seeds": [result["seed"] for result in results if result["returncode"] != 0],
    }
    summary_path = reports_dir / "randomized-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("\nRandomized seed summary")
    for result in results:
        print(f"- seed {result['seed']}: {result['status']} ({result['duration_seconds']}s)")

    if summary["failed_seeds"]:
        print(f"FAILED seeds: {', '.join(summary['failed_seeds'])}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
