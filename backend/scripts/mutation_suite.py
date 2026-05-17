"""Run the scoped mutmut profile and write a stable JSON report."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], *, output_path: Path | None = None) -> int:
    print(" ".join(shlex.quote(part) for part in cmd), flush=True)
    if output_path is None:
        result = subprocess.run(cmd, cwd=REPO_ROOT, check=False)
        return result.returncode

    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    output_path.write_text(result.stdout or "", encoding="utf-8")
    if result.stdout:
        print(result.stdout, end="")
    return result.returncode


def _int(stats: dict[str, Any], key: str) -> int:
    return int(stats.get(key, 0) or 0)


def _normalized_report(stats: dict[str, Any], returncodes: dict[str, int]) -> dict[str, Any]:
    total = _int(stats, "total")
    skipped = _int(stats, "skipped")
    killed = _int(stats, "killed")
    caught_by_type_check = _int(stats, "caught_by_type_check")
    survived = _int(stats, "survived")
    timeout = _int(stats, "timeout")
    incompetent = _int(stats, "incompetent") + _int(stats, "no_tests")
    suspicious = _int(stats, "suspicious")
    segfault = _int(stats, "segfault")
    interrupted = _int(stats, "check_was_interrupted_by_user")
    denominator = max(total - skipped, 0)
    killed_total = killed + caught_by_type_check
    score = 100.0 if denominator == 0 else (killed_total / denominator) * 100.0
    return {
        "total": total,
        "skipped": skipped,
        "killed": killed,
        "caught_by_type_check": caught_by_type_check,
        "survived": survived,
        "timeout": timeout,
        "incompetent": incompetent,
        "suspicious": suspicious,
        "segfault": segfault,
        "interrupted": interrupted,
        "score": round(score, 1),
        "returncodes": returncodes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--max-children", default="2")
    parser.add_argument("--min-score", type=float, default=65.0)
    parser.add_argument("--soft", action="store_true", help="report failures without failing")
    args = parser.parse_args()

    reports_dir = (REPO_ROOT / args.reports_dir).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    returncodes = {
        "run": _run([sys.executable, "-m", "mutmut", "run", "--max-children", args.max_children]),
        "export_cicd_stats": _run([sys.executable, "-m", "mutmut", "export-cicd-stats"]),
        "results": _run(
            [sys.executable, "-m", "mutmut", "results"],
            output_path=reports_dir / "mutmut-results.txt",
        ),
    }

    stats_path = REPO_ROOT / "mutants" / "mutmut-cicd-stats.json"
    if stats_path.exists():
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        report = _normalized_report(stats, returncodes)
    else:
        report = {
            "error": f"mutation stats not found: {stats_path.as_posix()}",
            "returncodes": returncodes,
        }

    report_path = reports_dir / "mutation-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("\nMutation summary")
    for key in ("killed", "survived", "timeout", "incompetent"):
        print(f"- {key}: {report.get(key, 0)}")
    if "score" in report:
        print(f"- score: {report['score']}%")

    failures: list[str] = []
    if any(code != 0 for code in returncodes.values()):
        failures.append("one or more mutmut commands returned non-zero")
    if "score" not in report:
        failures.append("mutation score unavailable")
    elif float(report["score"]) < args.min_score:
        failures.append(f"mutation score {report['score']}% < {args.min_score}%")
    if int(report.get("survived", 0)) > 0:
        failures.append(f"{report['survived']} mutants survived")

    if failures:
        for failure in failures:
            print(f"SOFT-FAIL: {failure}" if args.soft else f"FAIL: {failure}", file=sys.stderr)
        return 0 if args.soft else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
