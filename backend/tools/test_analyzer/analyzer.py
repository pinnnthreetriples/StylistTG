"""Core Analyzer class, baseline handling, and coverage integration."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, cast

from .models import (
    AnalyzerConfig,
    FileContext,
    Issue,
    Rule,
    Severity,
    parse_suppressions,
)
from .rules import ALL_RULES


class Analyzer:
    def __init__(
        self,
        config: AnalyzerConfig,
        rules: list[Rule] | None = None,
        coverage_data: dict[str, Any] | None = None,
    ) -> None:
        self.config = config
        self.rules = rules or ALL_RULES
        self.coverage_data = coverage_data

    def analyze_file(self, path: Path, base_dir: Path) -> list[Issue]:
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError, OSError:
            return []

        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []

        lines = source.splitlines()
        relative_path = str(path.relative_to(base_dir)).replace("\\", "/")

        line_supprs, file_supprs, supp_warnings = parse_suppressions(lines, relative_path)

        ctx = FileContext(
            path=path,
            relative_path=relative_path,
            source=source,
            tree=tree,
            lines=lines,
            suppressions=line_supprs,
            file_suppressions=file_supprs,
            suppression_warnings=supp_warnings,
        )

        # Filter suppression warnings (META001) through file-level suppressions too
        all_issues: list[Issue] = [w for w in supp_warnings if w.rule_id not in file_supprs]

        for rule in self.rules:
            # Skip disabled project rules
            if rule.id in self.config.project_rules_enabled:
                if not self.config.project_rules_enabled[rule.id]:
                    continue
            try:
                issues = rule.check(ctx, self.config)
            except Exception as exc:
                all_issues.append(
                    Issue(
                        rule_id="META002",
                        rule_type="analyzer",
                        severity=Severity.CRITICAL,
                        file=relative_path,
                        line=1,
                        message=(f"Analyzer rule {rule.id} crashed: {type(exc).__name__}: {exc}"),
                        recommendation=(
                            "Fix the analyzer rule before trusting this test-quality gate."
                        ),
                    )
                )
                continue
            for issue in issues:
                # Apply severity overrides from config
                if issue.rule_id in self.config.severity_overrides:
                    issue.severity = self.config.severity_overrides[issue.rule_id]
                # Apply suppressions
                if issue.rule_id in file_supprs:
                    continue
                line_key = str(issue.line)
                if line_key in line_supprs and issue.rule_id in line_supprs[line_key]:
                    continue
                all_issues.append(issue)

        return all_issues

    def analyze(self, path: Path, base_dir: Path | None = None) -> list[Issue]:
        if base_dir is None:
            base_dir = path if path.is_dir() else path.parent

        all_issues: list[Issue] = []

        if path.is_file():
            all_issues.extend(self.analyze_file(path, base_dir))
        elif path.is_dir():
            for py_file in sorted(path.rglob("*.py")):
                if py_file.name.startswith("test_") or py_file.name.endswith("_test.py"):
                    all_issues.extend(self.analyze_file(py_file, base_dir))

        return all_issues

    def coverage_branch_warnings(self) -> list[Issue]:
        issues: list[Issue] = []
        coverage_data = self.coverage_data or {}
        files = cast(dict[str, Any], coverage_data.get("files", {}))
        for filepath, info in files.items():
            file_info = cast(dict[str, Any], info)
            summary = cast(dict[str, Any], file_info.get("summary", {}))
            num_branches = int(summary.get("num_branches", 0) or 0)
            covered_branches = int(summary.get("covered_branches", 0) or 0)
            if num_branches > 0 and covered_branches < num_branches:
                missing = num_branches - covered_branches
                pct = round(covered_branches / num_branches * 100, 1)
                issues.append(
                    Issue(
                        rule_id="TQA040",
                        rule_type="edge_cases",
                        severity=Severity.INFO,
                        file=filepath,
                        line=1,
                        message=(
                            f"{missing} of {num_branches} branches"
                            f" uncovered ({pct}% branch coverage)"
                        ),
                        recommendation="Add tests for uncovered branches",
                    )
                )
        return issues


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------


def load_baseline(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {issue["fingerprint"] for issue in data.get("issues", [])}


def filter_by_baseline(issues: list[Issue], baseline: set[str]) -> list[Issue]:
    return [i for i in issues if i.fingerprint() not in baseline]


# ---------------------------------------------------------------------------
# Coverage integration
# ---------------------------------------------------------------------------


def load_coverage_context(coverage_path: Path) -> dict[str, Any] | None:
    if not coverage_path.exists():
        return None
    try:
        return json.loads(coverage_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError, OSError:
        return None
