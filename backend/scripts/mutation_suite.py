"""Run the scoped mutmut profile and write a stable JSON report."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(
    cmd: list[str],
    *,
    output_path: Path | None = None,
) -> int:
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


def _mutmut_cmd() -> list[str]:
    executable = shutil.which("mutmut")
    if executable:
        return [executable]
    return [sys.executable, "-m", "mutmut"]


def _count_result_status(results_path: Path, status: str) -> int:
    if not results_path.exists():
        return 0
    pattern = re.compile(rf":\s+{re.escape(status)}$")
    return sum(
        1 for line in results_path.read_text(encoding="utf-8").splitlines() if pattern.search(line)
    )


def _normalized_report(
    stats: dict[str, Any],
    returncodes: dict[str, int],
    *,
    results_path: Path,
) -> dict[str, Any]:
    total = _int(stats, "total")
    skipped = _int(stats, "skipped")
    killed = _int(stats, "killed")
    caught_by_type_check = _int(stats, "caught_by_type_check")
    survived = _int(stats, "survived")
    timeout = _int(stats, "timeout")
    incompetent = _int(stats, "incompetent") + _int(stats, "no_tests")
    not_checked = _count_result_status(results_path, "not checked")
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
        "not_checked": not_checked,
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
    results_path = reports_dir / "mutmut-results.txt"
    mutmut_cmd = _mutmut_cmd()

    returncodes = {
        "run": _run([*mutmut_cmd, "run", "--max-children", args.max_children]),
        "export_cicd_stats": _run([*mutmut_cmd, "export-cicd-stats"]),
        "results": _run(
            [*mutmut_cmd, "results"],
            output_path=results_path,
        ),
    }

    stats_path = REPO_ROOT / "mutants" / "mutmut-cicd-stats.json"
    if stats_path.exists():
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        report = _normalized_report(stats, returncodes, results_path=results_path)
        checked = sum(
            int(report.get(key, 0))
            for key in (
                "killed",
                "caught_by_type_check",
                "survived",
                "timeout",
                "incompetent",
                "suspicious",
                "segfault",
                "interrupted",
            )
        )
        if report["total"] > 0 and checked == 0 and report["not_checked"] > 0:
            report["error"] = (
                "mutmut generated mutants but did not check them; see mutmut-results.txt"
            )
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
    if "not_checked" in report:
        print(f"- not_checked: {report['not_checked']}")
    if "score" in report:
        print(f"- score: {report['score']}%")

    failures: list[str] = []
    if any(code != 0 for code in returncodes.values()):
        failures.append("one or more mutmut commands returned non-zero")
    if report.get("error"):
        failures.append(str(report["error"]))
    score = report.get("score")
    if not isinstance(score, int | float):
        failures.append("mutation score unavailable")
    elif float(score) < args.min_score:
        failures.append(f"mutation score {score}% < {args.min_score}%")
    survived = report.get("survived", 0)
    if isinstance(survived, int) and survived > 0:
        failures.append(f"{survived} mutants survived")

    if failures:
        for failure in failures:
            print(f"SOFT-FAIL: {failure}" if args.soft else f"FAIL: {failure}", file=sys.stderr)
        return 0 if args.soft else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
