"""Per-package coverage gate.

Reads `reports/coverage.json` (produced by `pytest --cov-report=json`)
and enforces per-package thresholds. Returns exit 1 if any package is
below its required line OR branch coverage.

Run via:
    python scripts/coverage_gate.py
or as part of local check / CI after pytest with --cov-branch.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

# Per-package thresholds. Format: (package_prefix, min_line_pct, min_branch_pct).
# Tighter thresholds for hot-path business logic; relaxed for adapters/storage
# that wrap external systems and are partly exercised by integration tests only.
# Ratchet thresholds: anchored at current measured coverage (rounded down).
# Any regression breaks the build. To raise the bar, lower numbers and re-run.
THRESHOLDS: list[tuple[str, float, float]] = [
    # package_prefix         line%   branch%
    ("app/api", 75.0, 49.0),  # FastAPI endpoints
    ("app/services", 78.0, 59.0),  # legacy/shared service layer
    ("app/modules", 88.0, 78.0),  # module-owned business features
    ("app/workers", 90.0, 80.0),  # background jobs — already strong
    ("app/job_queue", 69.0, 49.0),  # legacy RQ integration
    ("app/observability", 67.0, 70.0),  # Sentry/logging glue
    ("app/storage", 70.0, 43.0),  # S3/local FS wrappers
    ("app/adapters", 74.0, 55.0),  # external SDK wrappers (TDLib)
    ("tools/test_analyzer", 86.0, 67.0),  # our own quality tool
]


def _normalize(path: str) -> str:
    return path.replace("\\", "/")


def _pkg_for(path: str) -> str | None:
    norm = _normalize(path)
    for prefix, _line, _branch in THRESHOLDS:
        if norm.startswith(prefix + "/") or norm == prefix:
            return prefix
    return None


def _branch_pct(summary: dict[str, float | int]) -> float:
    num = int(summary.get("num_branches", 0) or 0)
    covered = int(summary.get("covered_branches", 0) or 0)
    if num == 0:
        # No branches in this file ⇒ treat as 100% branch coverage.
        return 100.0
    return (covered / num) * 100.0


def main() -> int:
    report_path = Path("reports/coverage.json")
    if not report_path.exists():
        print(
            f"ERROR: {report_path} not found. Run pytest with --cov-branch first.", file=sys.stderr
        )
        return 2

    data = json.loads(report_path.read_text(encoding="utf-8"))
    files = data["files"]

    # Aggregate covered_lines / num_statements per package (weighted avg, not per-file avg).
    agg: dict[str, dict[str, int]] = defaultdict(
        lambda: {"covered_lines": 0, "num_statements": 0, "covered_branches": 0, "num_branches": 0}
    )
    for path, info in files.items():
        pkg = _pkg_for(path)
        if pkg is None:
            continue
        s = info["summary"]
        agg[pkg]["covered_lines"] += int(s.get("covered_lines", 0))
        agg[pkg]["num_statements"] += int(s.get("num_statements", 0))
        agg[pkg]["covered_branches"] += int(s.get("covered_branches", 0))
        agg[pkg]["num_branches"] += int(s.get("num_branches", 0))

    failures: list[str] = []
    print(f"{'package':<28}{'line':>10}{'min':>10}{'branch':>10}{'min':>10}{'status':>10}")
    print("-" * 78)
    for prefix, min_line, min_branch in THRESHOLDS:
        bucket = agg.get(prefix)
        if bucket is None or bucket["num_statements"] == 0:
            print(
                f"{prefix:<28}{'n/a':>10}{min_line:>10.1f}{'n/a':>10}{min_branch:>10.1f}{'SKIP':>10}"
            )
            continue
        line_pct = (bucket["covered_lines"] / bucket["num_statements"]) * 100.0
        if bucket["num_branches"] == 0:
            branch_pct = 100.0
        else:
            branch_pct = (bucket["covered_branches"] / bucket["num_branches"]) * 100.0

        ok_line = line_pct >= min_line
        ok_branch = branch_pct >= min_branch
        status = "PASS" if (ok_line and ok_branch) else "FAIL"
        print(
            f"{prefix:<28}{line_pct:>9.1f}%{min_line:>9.1f}%{branch_pct:>9.1f}%{min_branch:>9.1f}%{status:>10}"
        )
        if not ok_line:
            failures.append(f"{prefix}: line {line_pct:.1f}% < {min_line:.1f}%")
        if not ok_branch:
            failures.append(f"{prefix}: branch {branch_pct:.1f}% < {min_branch:.1f}%")

    print("-" * 78)
    if failures:
        print("\nFAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("All per-package coverage thresholds met.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
