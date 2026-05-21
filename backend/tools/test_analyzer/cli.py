"""CLI entry point for the test quality analyzer."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .analyzer import Analyzer, filter_by_baseline, load_baseline, load_coverage_context
from .models import AnalyzerConfig, Issue, Severity
from .reporters import JsonReporter, SarifReporter, TextReporter
from .rules import ALL_RULES

REPORTERS = {
    "text": TextReporter,
    "json": JsonReporter,
    "sarif": SarifReporter,
}
REPORT_FILENAMES = {
    "text": "test-quality.txt",
    "json": "test-quality.json",
    "sarif": "test-quality.sarif",
}

RULE_EXPLANATIONS: dict[str, dict[str, str]] = {
    "TQA001": {
        "summary": "Test function has zero assertions",
        "bad": "def test_create():\n    service.create(name='x')",
        "good": (
            "def test_create():\n"
            "    result = service.create(name='x')\n"
            "    assert result.id is not None"
        ),
        "suppress": '# test-analyzer: disable=TQA001 reason="side-effect-only test"',
    },
    "TQA002": {
        "summary": "assert True / assertEqual(True, ...) — always passes",
        "bad": "def test_ok():\n    assert True",
        "good": "def test_ok():\n    assert result == expected",
        "suppress": '# test-analyzer: disable=TQA002 reason="placeholder"',
    },
    "TQA003": {
        "summary": "Self-equality assertion (assert x == x) — always passes",
        "bad": "assert resp == resp",
        "good": "assert resp == expected_resp",
        "suppress": '# test-analyzer: disable=TQA003 reason="identity check"',
    },
    "TQA004": {
        "summary": "Too many assertions in a single test function",
        "bad": "def test_all():\n    assert a; assert b; ... (>12 asserts)",
        "good": "Split into focused tests or parametrize",
        "suppress": '# test-analyzer: disable=TQA004 reason="integration contract"',
    },
    "TQA006": {
        "summary": "Manual try/except pattern instead of pytest.raises",
        "bad": "try:\n    func()\nexcept ValueError:\n    pass\nelse:\n    assert False",
        "good": "with pytest.raises(ValueError):\n    func()",
        "suppress": '# test-analyzer: disable=TQA006 reason="needs else branch"',
    },
    "TQA010": {
        "summary": "Flaky test — uses sleep()",
        "bad": "time.sleep(2); assert service.ready()",
        "good": "Use freezegun, a mocked clock, or deterministic state injection",
        "suppress": '# test-analyzer: disable=TQA010 reason="integration timing"',
    },
    "TQA012": {
        "summary": "datetime.now/utcnow without time freezer",
        "bad": "result = func(); assert result.created_at <= datetime.now()",
        "good": "with freeze_time('2024-01-01'):\n    result = func()",
        "suppress": '# test-analyzer: disable=TQA012 reason="wall clock ok here"',
    },
    "TQA013": {
        "summary": "HTTP call without integration marker or mock",
        "bad": "def test_api():\n    requests.get('https://example.com')",
        "good": "@pytest.mark.integration\ndef test_api(): ...",
        "suppress": '# test-analyzer: disable=TQA013 reason="intentional live call"',
    },
    "TQA020": {
        "summary": "Mock created but never asserted on",
        "bad": "m = Mock(); service.run(dep=m)  # no assert_called",
        "good": "m = Mock(); service.run(dep=m); m.send.assert_called_once()",
        "suppress": '# test-analyzer: disable=TQA020 reason="stub only"',
    },
    "TQA040": {
        "summary": "Uncovered branches detected from coverage report",
        "bad": "Source file has branches not exercised by any test",
        "good": "Add parametrized tests for uncovered branches",
        "suppress": "N/A — coverage-derived, not suppressible inline",
    },
    "STG001": {
        "summary": "dependency_overrides modified without try/finally cleanup",
        "bad": "app.dependency_overrides[dep] = mock\nclient.get(...) ",
        "good": (
            "try:\n    app.dependency_overrides[dep] = mock\n"
            "    ...\nfinally:\n    app.dependency_overrides.pop(dep)"
        ),
        "suppress": '# test-analyzer: disable=STG001 reason="app_client handles cleanup"',
    },
    "STG002": {
        "summary": "TestClient(app) + DB override without app_client helper",
        "bad": "app.dependency_overrides[get_db] = ...\nclient = TestClient(app)",
        "good": "with app_client(db_session) as client: ...",
        "suppress": '# test-analyzer: disable=STG002 reason="custom setup needed"',
    },
    "STG005": {
        "summary": "Live/integration test without env guard or pytest.skip",
        "bad": "@pytest.mark.live\ndef test_live(): ...",
        "good": (
            "@pytest.mark.live\ndef test_live():\n"
            "    if not os.getenv('CRED'):\n        pytest.skip('no creds')"
        ),
        "suppress": '# test-analyzer: disable=STG005 reason="CI always has creds"',
    },
    "STG006": {
        "summary": "S3 Stubber/mock-s3 used without context manager",
        "bad": "stubber = Stubber(s3)\nstubber.activate()",
        "good": "with Stubber(s3) as stubber: ...",
        "suppress": '# test-analyzer: disable=STG006 reason="manual lifecycle"',
    },
}


def _get_changed_files(ref: str) -> list[Path]:
    """Get list of changed test files relative to a git ref."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", ref],
            capture_output=True,
            text=True,
            check=True,
        )
        files: list[Path] = []
        for line in result.stdout.strip().splitlines():
            p = Path(line)
            if p.name.startswith("test_") or p.name.endswith("_test.py"):
                if p.exists():
                    files.append(p)
        return files
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def _parse_formats(raw: str) -> list[str]:
    formats = [item.strip().lower() for item in raw.split(",") if item.strip()]
    if not formats:
        msg = "--format must include at least one format"
        raise argparse.ArgumentTypeError(msg)
    invalid = [item for item in formats if item not in REPORTERS]
    if invalid:
        msg = f"unknown report format(s): {', '.join(invalid)}"
        raise argparse.ArgumentTypeError(msg)
    unique_formats: list[str] = []
    for item in formats:
        if item not in unique_formats:
            unique_formats.append(item)
    return unique_formats


def _write_reports(
    *,
    issues: list[Issue],
    formats: list[str],
    output: str | None,
    output_dir: str | None,
) -> None:
    if len(formats) > 1 and output:
        msg = "--output cannot be used with multiple --format values; use --output-dir"
        raise ValueError(msg)

    for format_name in formats:
        reporter = REPORTERS[format_name]()
        report = reporter.report(issues)
        out_path: Path | None = None
        if output:
            out_path = Path(output)
        elif output_dir:
            out_path = Path(output_dir) / REPORT_FILENAMES[format_name]

        if out_path:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(report, encoding="utf-8")
        elif len(formats) == 1:
            print(report)
        else:
            print(f"== {format_name} ==")
            print(report)


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915
    parser = argparse.ArgumentParser(
        prog="test-quality-analyzer",
        description="Static test quality analyzer for pytest suites",
    )
    parser.add_argument("--path", help="Path to test file or directory")
    parser.add_argument(
        "--format",
        type=_parse_formats,
        default=["text"],
        help="Output format: text, json, sarif, or comma-separated list such as sarif,json",
    )
    parser.add_argument("--output", help="Output file path for a single format (stdout if omitted)")
    parser.add_argument(
        "--output-dir",
        help="Directory for multi-format output using stable test-quality.* filenames",
    )
    parser.add_argument(
        "--severity",
        choices=["INFO", "WARNING", "CRITICAL"],
        default="INFO",
        help="Minimum severity to include in reports",
    )
    parser.add_argument(
        "--fail-on-severity",
        choices=["INFO", "WARNING", "CRITICAL"],
        help=(
            "Minimum severity that makes the process exit non-zero. "
            "Defaults to --severity."
        ),
    )
    parser.add_argument("--baseline", help="Path to baseline JSON file")
    parser.add_argument("--config", help="Path to test-quality.toml config")
    parser.add_argument("--coverage", help="Path to coverage JSON report")
    parser.add_argument(
        "--explain",
        metavar="RULE_ID",
        help="Show explanation for a rule and exit",
    )
    parser.add_argument(
        "--changed",
        metavar="REF",
        help="Only analyze test files changed vs REF (e.g. origin/main)",
    )

    args = parser.parse_args(argv)

    if args.explain:
        rule_id = args.explain.upper()
        info = RULE_EXPLANATIONS.get(rule_id)
        if not info:
            found = next((r for r in ALL_RULES if r.id == rule_id), None)
            if found:
                print(f"Rule: {found.id}")
                print(f"Type: {found.type}")
                print(f"Severity: {found.default_severity.name}")
                print("(No detailed explanation available yet)")
            else:
                print(f"Unknown rule: {rule_id}", file=sys.stderr)
                return 2
            return 0
        print(f"Rule: {rule_id}")
        print(f"Summary: {info['summary']}")
        print("\n✗ Bad:")
        print(f"  {info['bad']}")
        print("\n✓ Good:")
        print(f"  {info['good']}")
        print("\nSuppress:")
        print(f"  {info['suppress']}")
        return 0

    if not args.path:
        parser.error("--path is required (or use --explain RULE_ID)")

    config_path = Path(args.config) if args.config else Path("test-quality.toml")
    if config_path.exists():
        config = AnalyzerConfig.from_toml(config_path)
    else:
        config = AnalyzerConfig()

    target = Path(args.path)
    if not target.exists():
        print(f"Error: path '{args.path}' does not exist", file=sys.stderr)
        return 2

    base_dir = target if target.is_dir() else target.parent

    coverage_data = None
    if args.coverage:
        coverage_data = load_coverage_context(Path(args.coverage))

    analyzer = Analyzer(config, coverage_data=coverage_data)
    try:
        if args.changed:
            changed_files = _get_changed_files(args.changed)
            issues: list[Issue] = []
            for f in changed_files:
                if f.is_relative_to(target):
                    issues.extend(analyzer.analyze_file(f, base_dir))
        else:
            issues = analyzer.analyze(target, base_dir)
    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        return 2

    if args.baseline:
        baseline = load_baseline(Path(args.baseline))
        issues = filter_by_baseline(issues, baseline)

    report_min_severity = Severity.from_str(args.severity)
    fail_min_severity = Severity.from_str(args.fail_on_severity or args.severity)
    reported_issues = [i for i in issues if i.severity >= report_min_severity]
    failing_issues = [i for i in issues if i.severity >= fail_min_severity]

    try:
        _write_reports(
            issues=reported_issues,
            formats=args.format,
            output=args.output,
            output_dir=args.output_dir,
        )
    except ValueError as exc:
        parser.error(str(exc))

    return 1 if failing_issues else 0
