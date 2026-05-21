"""Local backend quality gate aligned with CI/Test Quality checks.

Usage:
    python scripts/check.py            # run the standard PR/local gate
    python scripts/check.py --fast     # skip slow standard checks
    python scripts/check.py --skip pyright pip-audit
    python scripts/check.py --only ruff analyzer
    python scripts/check.py --only nightly-randomized
    python scripts/check.py --only mutation
    python scripts/check.py --nightly  # run nightly-heavy local profiles

CI installs narrow quality extras per job. Local pre-push expects the full dev environment.
Run the standard gate before every push. Nightly-heavy checks are opt-in only.
Exit code reflects worst single check (0 = all pass, 1 = any fail, 2 = setup error).
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Check:
    name: str
    cmd: list[str]
    cwd: Path
    # If True, a non-zero exit is reported but does not fail the overall gate.
    # Use for checks that have a known backlog (e.g. pyright strict on legacy code).
    soft: bool = False


STANDARD_CHECKS: list[Check] = [
    Check("ruff-lint", [sys.executable, "-m", "ruff", "check", "."], REPO_ROOT),
    Check("ruff-format", [sys.executable, "-m", "ruff", "format", "--check", "."], REPO_ROOT),
    Check(
        "pyright-ci",
        [
            sys.executable,
            "-m",
            "pyright",
            "app/api",
            "app/services",
            "app/schemas.py",
            "app/config.py",
            "app/workers",
        ],
        REPO_ROOT,
    ),
    Check("pyright-strict", [sys.executable, "-m", "pyright"], REPO_ROOT, soft=True),
    Check(
        "pytest+coverage",
        [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "-q",
            "--no-header",
            "-n",
            "auto",
            "--dist=loadscope",
            "--cov=app",
            "--cov=tools",
            "--cov-branch",
            "--cov-context=test",
            "--cov-report=json:reports/coverage.json",
            "--cov-report=term-missing:skip-covered",
        ],
        REPO_ROOT,
    ),
    Check("coverage-gate", [sys.executable, "scripts/coverage_gate.py"], REPO_ROOT),
    Check(
        "test-analyzer",
        [
            sys.executable,
            "-m",
            "tools.test_analyzer",
            "--path",
            "tests",
            "--coverage",
            "reports/coverage.json",
            "--severity",
            "INFO",
        ],
        REPO_ROOT,
    ),
    Check(
        "pip-audit",
        # --skip-editable: don't try to audit our own editable install.
        # Plain mode (no --strict) returns exit 1 only on real CVEs, which is
        # exactly the failure condition we want.
        [sys.executable, "-m", "pip_audit", "--skip-editable", "--progress-spinner=off"],
        REPO_ROOT,
    ),
    Check(
        "complexity",
        [
            sys.executable,
            "-m",
            "xenon",
            "--max-absolute",
            "B",
            "--max-modules",
            "A",
            "--max-average",
            "A",
            "app",
            "tools",
            "scripts",
        ],
        REPO_ROOT,
        soft=True,
    ),
]


NIGHTLY_CHECKS: list[Check] = [
    Check(
        "nightly-randomized",
        [sys.executable, "scripts/nightly_randomized.py"],
        REPO_ROOT,
    ),
    Check(
        "mutation",
        [sys.executable, "scripts/mutation_suite.py", "--soft"],
        REPO_ROOT,
        soft=True,
    ),
]

CHECKS_BY_NAME: dict[str, Check] = {
    check.name: check for check in [*STANDARD_CHECKS, *NIGHTLY_CHECKS]
}


def _run(check: Check, verbose: bool) -> tuple[bool, float]:
    start = time.monotonic()
    print(f"\n=== [{check.name}] {' '.join(shlex.quote(p) for p in check.cmd)}", flush=True)
    try:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        result = subprocess.run(
            check.cmd,
            cwd=check.cwd,
            check=False,
            env=env,
            stdout=None if verbose else subprocess.PIPE,
            stderr=None if verbose else subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError as exc:
        print(f"  ERROR: command not found: {exc}", file=sys.stderr)
        return False, time.monotonic() - start

    elapsed = time.monotonic() - start
    if result.returncode == 0:
        print(f"  PASS {check.name} ({elapsed:.1f}s)")
        return True, elapsed

    if not verbose and result.stdout:
        # Show output only on failure to keep happy-path quiet.
        sys.stdout.write(result.stdout)
        sys.stdout.write("\n")

    severity = "SOFT-FAIL" if check.soft else "FAIL"
    print(f"  {severity} {check.name} ({elapsed:.1f}s) [exit={result.returncode}]")
    return check.soft, elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fast", action="store_true", help="skip slow checks (pyright, coverage-gate, pip-audit)"
    )
    parser.add_argument("--skip", nargs="+", default=[], help="check names to skip")
    parser.add_argument("--only", nargs="+", default=[], help="run only these check names")
    parser.add_argument("--nightly", action="store_true", help="run nightly-heavy local profiles")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="stream subprocess output live"
    )
    args = parser.parse_args()

    fast_skip = (
        {"pyright-ci", "pyright-strict", "coverage-gate", "pip-audit", "complexity"}
        if args.fast
        else set()
    )
    skip = set(args.skip) | fast_skip
    only = set(args.only)

    if only:
        unknown = sorted(only - CHECKS_BY_NAME.keys())
        if unknown:
            print(f"Unknown check(s): {', '.join(unknown)}", file=sys.stderr)
            return 2
        candidate_checks = [CHECKS_BY_NAME[name] for name in args.only]
    else:
        candidate_checks = NIGHTLY_CHECKS if args.nightly else STANDARD_CHECKS

    to_run: list[Check] = []
    for c in candidate_checks:
        if c.name in skip:
            continue
        to_run.append(c)

    if not to_run:
        print("No checks selected.", file=sys.stderr)
        return 2

    print(f"Running {len(to_run)} check(s) in {REPO_ROOT}")

    failures: list[str] = []
    total_elapsed = 0.0
    for c in to_run:
        ok, elapsed = _run(c, verbose=args.verbose)
        total_elapsed += elapsed
        if not ok:
            failures.append(c.name)

    print("\n" + "=" * 60)
    if failures:
        print(f"GATE FAILED ({len(failures)} hard fail) - total {total_elapsed:.1f}s")
        for name in failures:
            print(f"  - {name}")
        return 1

    print(f"GATE PASSED ({len(to_run)} checks) - total {total_elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
