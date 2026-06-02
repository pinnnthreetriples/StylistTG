"""Quality dashboard / trend snapshot generator (issue #275).

Reads the machine-readable artifacts produced by the PR and nightly
workflows and emits two files:

- ``reports/quality-snapshot.json`` — trend-friendly snapshot
  (commit, timestamp, totals for coverage / analyzer findings /
  slow tests / contract / mutation if present).
- ``reports/quality-summary.md`` — human-readable Markdown summary
  intended for the PR check page and the GitHub Actions step
  summary (``$GITHUB_STEP_SUMMARY``).

The script depends only on the standard library so it can run in any
job without pulling extra extras.

Example::

    uv run python scripts/quality_dashboard.py \
        --reports-dir reports \
        --output-json reports/quality-snapshot.json \
        --output-md reports/quality-summary.md

External trend stores (Grafana / BigQuery / S3) are out of scope for
this slice — the JSON snapshot is the wire format any future store can
consume.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _coverage_totals(coverage: dict | None) -> dict[str, Any]:
    if not coverage:
        return {"available": False}
    totals = coverage.get("totals") or {}
    num_branches = int(totals.get("num_branches") or 0)
    covered_branches = int(totals.get("covered_branches") or 0)
    missing_branches = int(totals.get("missing_branches") or 0)
    # Recompute branch percentage from raw counts — percent_covered_display
    # is a *display* rounding of LINE coverage in coverage.py and is not
    # a branch metric; mixing it in here under-reported branch progress.
    if num_branches > 0:
        percent_branch: float = (covered_branches / num_branches) * 100.0
    else:
        percent_branch = 100.0
    return {
        "available": True,
        "branch_coverage": bool((coverage.get("meta") or {}).get("branch_coverage")),
        "percent_covered": float(totals.get("percent_covered") or 0.0),
        "percent_branch": round(percent_branch, 1),
        "num_statements": int(totals.get("num_statements") or 0),
        "missing_lines": int(totals.get("missing_lines") or 0),
        "num_branches": num_branches,
        "covered_branches": covered_branches,
        "missing_branches": missing_branches,
    }


def _analyzer_totals(report: Any) -> dict[str, Any]:
    if not report:
        return {"available": False, "total": 0, "by_severity": {}, "by_rule": {}}
    issues = report.get("issues") if isinstance(report, dict) else report
    if not isinstance(issues, list):
        return {"available": False, "total": 0, "by_severity": {}, "by_rule": {}}
    by_severity: Counter[str] = Counter()
    by_rule: Counter[str] = Counter()
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        by_severity[str(issue.get("severity", "INFO"))] += 1
        by_rule[str(issue.get("rule_id", "?"))] += 1
    return {
        "available": True,
        "total": sum(by_severity.values()),
        "by_severity": dict(by_severity),
        "by_rule": dict(by_rule.most_common(10)),
    }


def _slow_test_totals(report: Any) -> dict[str, Any]:
    if not report:
        return {"available": False, "total": 0}
    entries = report.get("entries") if isinstance(report, dict) else report
    if not isinstance(entries, list):
        return {"available": False, "total": 0}
    return {
        "available": True,
        "total": len(entries),
        "max_call_seconds": max(
            (
                float(e.get("seconds") or 0.0)
                for e in entries
                if str(e.get("phase", "call")) == "call"
            ),
            default=0.0,
        ),
    }


def _mutation_totals(report: Any) -> dict[str, Any]:
    if not report or not isinstance(report, dict):
        return {"available": False}
    return {
        "available": True,
        "score": report.get("score"),
        "killed": report.get("killed"),
        "survived": report.get("survived"),
        "timeout": report.get("timeout"),
        "incompetent": report.get("incompetent"),
    }


# Per-profile required reports. A profile's status is "incomplete" if any
# required report is absent — the dashboard must not silently hide missing
# data behind `available: false`.
REQUIRED_REPORTS: dict[str, tuple[str, ...]] = {
    "pr": ("coverage", "analyzer", "slow_tests"),
    "nightly": ("coverage", "analyzer", "slow_tests", "mutation"),
}


def _load_analyzer(reports_dir: Path) -> Any:
    # The CLI default filename is `test-quality.json`. Fall back to the
    # historical/alt name `test-analyzer.json` for resilience.
    for name in ("test-quality.json", "test-analyzer.json"):
        report = _load_json(reports_dir / name)
        if report is not None:
            return report
    return None


def build_snapshot(reports_dir: Path, *, profile: str = "pr") -> dict[str, Any]:
    coverage = _load_json(reports_dir / "coverage.json")
    analyzer = _load_analyzer(reports_dir)
    slow = _load_json(reports_dir / "slow-tests.json")
    mutation = _load_json(reports_dir / "mutation-report.json")

    sections: dict[str, dict[str, Any]] = {
        "coverage": _coverage_totals(coverage),
        "analyzer": _analyzer_totals(analyzer),
        "slow_tests": _slow_test_totals(slow),
        "mutation": _mutation_totals(mutation),
    }

    required = REQUIRED_REPORTS.get(profile, ())
    missing_required = sorted(
        section for section in required if not sections[section].get("available")
    )
    status = "ok" if not missing_required else "incomplete"

    return {
        "schema_version": 2,
        "generated_at": datetime.now(UTC).isoformat(),
        "profile": profile,
        "status": status,
        "missing_required_reports": missing_required,
        "git_sha": os.environ.get("GITHUB_SHA", "")[:12] or None,
        "git_ref": os.environ.get("GITHUB_REF", "") or None,
        "workflow": os.environ.get("GITHUB_WORKFLOW", "") or None,
        "run_id": os.environ.get("GITHUB_RUN_ID", "") or None,
        **sections,
    }


def _table(rows: list[tuple[str, str]]) -> str:
    width = max((len(name) for name, _ in rows), default=8)
    lines = [f"| {'Metric':<{width}} | Value |", f"|{'-' * (width + 2)}|-------|"]
    for name, value in rows:
        lines.append(f"| {name:<{width}} | {value} |")
    return "\n".join(lines)


def render_markdown(snapshot: dict[str, Any]) -> str:
    coverage = snapshot.get("coverage", {})
    analyzer = snapshot.get("analyzer", {})
    slow = snapshot.get("slow_tests", {})
    mutation = snapshot.get("mutation", {})

    lines: list[str] = ["# StylistTG quality snapshot", ""]
    lines.append(f"_generated_ `{snapshot.get('generated_at')}`")
    if snapshot.get("git_sha"):
        lines.append(f"_sha_ `{snapshot['git_sha']}`")
    lines.append("")

    if snapshot.get("status") == "incomplete":
        lines.append(
            "> :warning: **status: incomplete** — required reports missing: "
            f"`{', '.join(snapshot.get('missing_required_reports') or [])}`. "
            "The PR/nightly profile should fail until they are produced."
        )
        lines.append("")

    if coverage.get("available"):
        lines.append("## Coverage")
        lines.append("")
        lines.append(
            _table(
                [
                    ("Line %", f"{coverage['percent_covered']:.1f}%"),
                    ("Branch %", f"{coverage['percent_branch']:.1f}%"),
                    ("Branch enabled", "yes" if coverage.get("branch_coverage") else "no"),
                    ("Statements", str(coverage["num_statements"])),
                    ("Missing", str(coverage["missing_lines"])),
                    ("Branches", str(coverage["num_branches"])),
                    ("Missing branches", str(coverage["missing_branches"])),
                ]
            )
        )
        lines.append("")
    else:
        lines.append("_coverage.json not available_\n")

    if analyzer.get("available"):
        lines.append("## Analyzer findings")
        lines.append("")
        sev = analyzer.get("by_severity", {})
        lines.append(
            _table(
                [
                    ("Total", str(analyzer["total"])),
                    ("CRITICAL", str(sev.get("CRITICAL", 0))),
                    ("WARNING", str(sev.get("WARNING", 0))),
                    ("INFO", str(sev.get("INFO", 0))),
                ]
            )
        )
        top = analyzer.get("by_rule", {})
        if top:
            lines.append("")
            lines.append("Top rules:")
            for rule_id, count in top.items():
                lines.append(f"- `{rule_id}`: {count}")
        lines.append("")
    else:
        lines.append("_test-quality.json not available_\n")

    if slow.get("available"):
        lines.append("## Slow tests")
        lines.append("")
        lines.append(
            _table(
                [
                    ("Slow entries", str(slow["total"])),
                    ("Max call (s)", f"{slow['max_call_seconds']:.2f}"),
                ]
            )
        )
        lines.append("")

    if mutation.get("available"):
        lines.append("## Mutation (nightly)")
        lines.append("")
        lines.append(
            _table(
                [
                    ("Score %", str(mutation.get("score", "n/a"))),
                    ("Killed", str(mutation.get("killed", 0))),
                    ("Survived", str(mutation.get("survived", 0))),
                    ("Timeout", str(mutation.get("timeout", 0))),
                ]
            )
        )
        lines.append("")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--output-json", default="reports/quality-snapshot.json")
    parser.add_argument("--output-md", default="reports/quality-summary.md")
    parser.add_argument(
        "--profile",
        default="pr",
        choices=sorted(REQUIRED_REPORTS),
        help="Required-report set for this run (pr|nightly). Missing required "
        "reports flip status to 'incomplete' and (with --fail-on-incomplete) "
        "exit non-zero.",
    )
    parser.add_argument(
        "--fail-on-incomplete",
        action="store_true",
        help=(
            "Exit 2 when status='incomplete'. Set this in PR/nightly "
            "workflows so a missing required report fails the dashboard "
            "step instead of producing a green page with `available: false`."
        ),
    )
    args = parser.parse_args(argv)

    reports_dir = Path(args.reports_dir)
    snapshot = build_snapshot(reports_dir, profile=args.profile)

    Path(args.output_json).write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    Path(args.output_md).write_text(render_markdown(snapshot), encoding="utf-8")
    print(f"wrote {args.output_json} and {args.output_md}")

    if args.fail_on_incomplete and snapshot["status"] != "ok":
        print(
            f"FAIL: quality snapshot status={snapshot['status']}, missing "
            f"required reports: {snapshot['missing_required_reports']}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
