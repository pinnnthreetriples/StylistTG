"""
Static test quality analyzer for pytest/unittest suites.

Examples:
    python tools/test_analyzer.py --path tests
    python tools/test_analyzer.py --path tests/test_api.py
    python tools/test_analyzer.py --path tests --format json --output reports/test-quality.json
    python tools/test_analyzer.py --path tests --format sarif --output reports/test-quality.sarif
    python tools/test_analyzer.py --path tests --baseline reports/test-quality-baseline.json

Exit codes:
    0: no CRITICAL issues
    1: CRITICAL issues found
    2: CLI/analyzer error

Suppressions:
    # test-analyzer: disable=TQA011 reason="..."
    # test-analyzer: disable-file=TQA030 reason="..."
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import tomllib
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------


class Severity(IntEnum):
    INFO = 0
    WARNING = 1
    CRITICAL = 2

    @classmethod
    def from_str(cls, s: str) -> "Severity":
        return cls[s.upper()]


@dataclass
class Issue:
    rule_id: str
    rule_type: str
    severity: Severity
    file: str
    line: int
    message: str
    recommendation: str

    def fingerprint(self) -> str:
        content = f"{self.rule_id}:{self.file}:{self.line}:{self.message}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class FileContext:
    path: Path
    relative_path: str
    source: str
    tree: ast.AST
    lines: list[str]
    suppressions: dict[str, set[str]]  # line_or_file -> set of rule_ids
    file_suppressions: set[str]
    suppression_warnings: list[Issue]


@dataclass
class AnalyzerConfig:
    tests_paths: list[str] = field(default_factory=lambda: ["tests"])
    source_paths: list[str] = field(default_factory=lambda: ["app"])
    external_markers: list[str] = field(
        default_factory=lambda: ["live", "integration", "redis", "postgres", "slow"]
    )
    max_assertions_per_test: int = 12
    duplicate_min_lines: int = 7
    duplicate_similarity: float = 0.90
    severity_overrides: dict[str, Severity] = field(default_factory=dict)
    project_rules_enabled: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def from_toml(cls, path: Path) -> "AnalyzerConfig":
        with open(path, "rb") as f:
            data = tomllib.load(f)
        config = cls()
        if "paths" in data:
            config.tests_paths = data["paths"].get("tests", config.tests_paths)
            config.source_paths = data["paths"].get("source", config.source_paths)
        if "pytest" in data:
            config.external_markers = data["pytest"].get(
                "external_markers", config.external_markers
            )
        if "thresholds" in data:
            config.max_assertions_per_test = data["thresholds"].get(
                "max_assertions_per_test", config.max_assertions_per_test
            )
            config.duplicate_min_lines = data["thresholds"].get(
                "duplicate_min_lines", config.duplicate_min_lines
            )
            config.duplicate_similarity = data["thresholds"].get(
                "duplicate_similarity", config.duplicate_similarity
            )
        if "severity" in data:
            for key, val in data["severity"].items():
                config.severity_overrides[key] = Severity.from_str(val)
        if "project_rules" in data:
            config.project_rules_enabled = data["project_rules"]
        return config


# ---------------------------------------------------------------------------
# Rule base class
# ---------------------------------------------------------------------------


class Rule:
    id: str = ""
    type: str = ""
    default_severity: Severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SUPPRESSION_RE = re.compile(
    r"#\s*test-analyzer:\s*disable=(\w+)(?:\s+reason=\"([^\"]*)\")?"
)
_FILE_SUPPRESSION_RE = re.compile(
    r"#\s*test-analyzer:\s*disable-file=(\w+)(?:\s+reason=\"([^\"]*)\")?"
)


def _parse_suppressions(
    lines: list[str], relative_path: str,
) -> tuple[dict[str, set[str]], set[str], list[Issue]]:
    """Parse inline and file-level suppressions, return (line_supprs, file_supprs, warnings)."""
    line_suppressions: dict[str, set[str]] = {}
    file_suppressions: set[str] = set()
    warnings: list[Issue] = []

    for i, line in enumerate(lines, 1):
        m = _FILE_SUPPRESSION_RE.search(line)
        if m:
            rule_id = m.group(1)
            reason = m.group(2)
            file_suppressions.add(rule_id)
            if not reason:
                warnings.append(Issue(
                    rule_id="META001",
                    rule_type="meta",
                    severity=Severity.WARNING,
                    file=relative_path,
                    line=i,
                    message=f"Suppression for {rule_id} without reason=",
                    recommendation="Add reason=\"...\" to suppression comment",
                ))
            continue
        m = _SUPPRESSION_RE.search(line)
        if m:
            rule_id = m.group(1)
            reason = m.group(2)
            key = str(i + 1)  # suppression applies to next line
            line_suppressions.setdefault(key, set()).add(rule_id)
            if not reason:
                warnings.append(Issue(
                    rule_id="META001",
                    rule_type="meta",
                    severity=Severity.WARNING,
                    file=relative_path,
                    line=i,
                    message=f"Suppression for {rule_id} without reason=",
                    recommendation="Add reason=\"...\" to suppression comment",
                ))
    return line_suppressions, file_suppressions, warnings


def _is_test_function(node: ast.FunctionDef) -> bool:
    return node.name.startswith("test_")


def _get_test_functions(tree: ast.AST) -> list[ast.FunctionDef]:
    funcs: list[ast.FunctionDef] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_test_function(node):
                funcs.append(node)
    return funcs


def _count_asserts(node: ast.AST) -> int:
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            count += 1
        elif isinstance(child, ast.Call):
            func = child.func
            if (
                (isinstance(func, ast.Attribute) and func.attr.startswith("assert"))
                or (isinstance(func, ast.Name) and func.id.startswith("assert"))
            ):
                count += 1
    return count


def _has_decorator(func: ast.FunctionDef, name: str) -> bool:
    for dec in func.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == name:
            return True
        if isinstance(dec, ast.Attribute) and dec.attr == name:
            return True
        if isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Attribute) and dec.func.attr == name:
                return True
            if isinstance(dec.func, ast.Name) and dec.func.id == name:
                return True
    return False


def _has_marker(func: ast.FunctionDef, marker: str) -> bool:
    for dec in func.decorator_list:
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            if dec.func.attr == marker:
                return True
            if dec.func.attr == "mark":
                # @pytest.mark.live style
                pass
        if isinstance(dec, ast.Attribute):
            if dec.attr == marker:
                return True
    # Check pytest.mark.X pattern
    for dec in func.decorator_list:
        dec_src = ast.dump(dec)
        if f"attr='{marker}'" in dec_src:
            return True
    return False


def _func_source(func: ast.FunctionDef, lines: list[str]) -> str:
    start = func.lineno - 1
    end = func.end_lineno or start + 1
    return "\n".join(lines[start:end])


# ---------------------------------------------------------------------------
# Generic Rules: Assertions
# ---------------------------------------------------------------------------


class ZeroAssertions(Rule):
    id = "TQA001"
    type = "assertions"
    default_severity = Severity.CRITICAL

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            if _count_asserts(func) == 0:
                # Check for pytest.raises usage (that counts as assertion)
                src = _func_source(func, ctx.lines)
                if "pytest.raises" not in src and "assertRaises" not in src:
                    issues.append(Issue(
                        rule_id=self.id,
                        rule_type=self.type,
                        severity=self.default_severity,
                        file=ctx.relative_path,
                        line=func.lineno,
                        message=f"Test `{func.name}` has zero assertions",
                        recommendation="Add assert statements or use pytest.raises",
                    ))
        return issues


class AssertTrue(Rule):
    id = "TQA002"
    type = "assertions"
    default_severity = Severity.CRITICAL

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            for node in ast.walk(func):
                if isinstance(node, ast.Assert):
                    if isinstance(node.test, ast.Constant) and node.test.value is True:
                        issues.append(Issue(
                            rule_id=self.id,
                            rule_type=self.type,
                            severity=self.default_severity,
                            file=ctx.relative_path,
                            line=node.lineno,
                            message="`assert True` is a no-op assertion",
                            recommendation="Replace with a meaningful assertion",
                        ))
        return issues


class AssertSelfEquality(Rule):
    id = "TQA003"
    type = "assertions"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            for node in ast.walk(func):
                if isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare):
                    if (
                        len(node.test.ops) == 1
                        and isinstance(node.test.ops[0], ast.Eq)
                        and len(node.test.comparators) == 1
                    ):
                        left = ast.dump(node.test.left)
                        right = ast.dump(node.test.comparators[0])
                        if left == right:
                            issues.append(Issue(
                                rule_id=self.id,
                                rule_type=self.type,
                                severity=self.default_severity,
                                file=ctx.relative_path,
                                line=node.lineno,
                                message="`assert x == x` is always true",
                                recommendation="Compare against expected value",
                            ))
        return issues


class TooManyAssertions(Rule):
    id = "TQA004"
    type = "assertions"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        limit = config.max_assertions_per_test
        for func in _get_test_functions(ctx.tree):
            count = _count_asserts(func)
            if count > limit:
                issues.append(Issue(
                    rule_id=self.id,
                    rule_type=self.type,
                    severity=self.default_severity,
                    file=ctx.relative_path,
                    line=func.lineno,
                    message=f"Test `{func.name}` has {count} assertions (max {limit})",
                    recommendation="Split into focused tests or extract helper",
                ))
        return issues


class UnittestAssertTrue(Rule):
    id = "TQA005"
    type = "assertions"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            for node in ast.walk(func):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr == "assertEqual" and len(node.args) >= 2:
                        arg = node.args[0]
                        if isinstance(arg, ast.Constant) and arg.value is True:
                            issues.append(Issue(
                                rule_id=self.id,
                                rule_type=self.type,
                                severity=self.default_severity,
                                file=ctx.relative_path,
                                line=node.lineno,
                                message=(
                                    "unittest assertEqual(True, ...)"
                                    " \u2014 prefer assertTrue or assert"
                                ),
                                recommendation="Use assertTrue() or plain assert",
                            ))
        return issues


class ManualExceptionCatch(Rule):
    id = "TQA006"
    type = "assertions"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            for node in ast.walk(func):
                if isinstance(node, ast.Try):
                    for _handler in node.handlers:
                        # Pattern: try/except SomeError + else with pytest.fail or assert False
                        if node.orelse:
                            for stmt in node.orelse:
                                src = ast.dump(stmt)
                                if "pytest.fail" in src or (
                                    isinstance(stmt, ast.Assert)
                                    and isinstance(stmt.test, ast.Constant)
                                    and stmt.test.value is False
                                ):
                                    issues.append(Issue(
                                        rule_id=self.id,
                                        rule_type=self.type,
                                        severity=self.default_severity,
                                        file=ctx.relative_path,
                                        line=node.lineno,
                                        message="Manual try/except/else for expected exception",
                                        recommendation="Use pytest.raises() context manager",
                                    ))
                                    break
        return issues


# ---------------------------------------------------------------------------
# Generic Rules: Flaky
# ---------------------------------------------------------------------------


class TimeSleep(Rule):
    id = "TQA010"
    type = "flaky"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            for node in ast.walk(func):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr == "sleep" and isinstance(node.func.value, ast.Name):
                        if node.func.value.id == "time":
                            issues.append(Issue(
                                rule_id=self.id,
                                rule_type=self.type,
                                severity=self.default_severity,
                                file=ctx.relative_path,
                                line=node.lineno,
                                message="time.sleep() in test makes it flaky/slow",
                                recommendation="Use freezegun, mock clock, or remove sleep",
                            ))
        return issues


class RandomWithoutSeed(Rule):
    id = "TQA011"
    type = "flaky"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            src = _func_source(func, ctx.lines)
            if "random." in src and "seed" not in src:
                issues.append(Issue(
                    rule_id=self.id,
                    rule_type=self.type,
                    severity=self.default_severity,
                    file=ctx.relative_path,
                    line=func.lineno,
                    message=f"Test `{func.name}` uses random without deterministic seed",
                    recommendation="Set random.seed() or use hypothesis",
                ))
        return issues


class DatetimeNow(Rule):
    id = "TQA012"
    type = "flaky"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            for node in ast.walk(func):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("now", "utcnow"):
                        src = _func_source(func, ctx.lines)
                        if (
                            "freeze_time" not in src
                            and "monkeypatch" not in src
                            and "freezegun" not in src
                        ):
                            issues.append(Issue(
                                rule_id=self.id,
                                rule_type=self.type,
                                severity=self.default_severity,
                                file=ctx.relative_path,
                                line=node.lineno,
                                message="datetime.now/utcnow without time freezer",
                                recommendation="Use freezegun or monkeypatch time source",
                            ))
        return issues


class ExternalHTTPWithoutMarker(Rule):
    id = "TQA013"
    type = "flaky"
    default_severity = Severity.CRITICAL

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        http_patterns = [
            "requests.get", "requests.post",
            "httpx.get", "httpx.post", "urllib.request",
        ]
        for func in _get_test_functions(ctx.tree):
            src = _func_source(func, ctx.lines)
            has_http = any(p in src for p in http_patterns)
            if has_http:
                has_marker = any(
                    _has_marker(func, m) for m in config.external_markers
                )
                if not has_marker and "mock" not in src.lower() and "patch" not in src.lower():
                    issues.append(Issue(
                        rule_id=self.id,
                        rule_type=self.type,
                        severity=self.default_severity,
                        file=ctx.relative_path,
                        line=func.lineno,
                        message=(
                            f"Test `{func.name}` makes HTTP call without"
                            " integration marker or mock"
                        ),
                        recommendation="Add @pytest.mark.integration or mock the HTTP client",
                    ))
        return issues


class FilesystemWriteOutsideTmp(Rule):
    id = "TQA014"
    type = "flaky"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            src = _func_source(func, ctx.lines)
            if "open(" in src and ("'w'" in src or "\"w\"" in src):
                if "tmp_path" not in src and "tmpdir" not in src and "tmp" not in src.lower():
                    issues.append(Issue(
                        rule_id=self.id,
                        rule_type=self.type,
                        severity=self.default_severity,
                        file=ctx.relative_path,
                        line=func.lineno,
                        message=f"Test `{func.name}` writes to filesystem outside tmp_path",
                        recommendation="Use tmp_path fixture or tmpdir",
                    ))
        return issues


# ---------------------------------------------------------------------------
# Generic Rules: Mocks
# ---------------------------------------------------------------------------


class MockWithoutAssert(Rule):
    id = "TQA020"
    type = "mocks"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            src = _func_source(func, ctx.lines)
            if "MagicMock(" in src or "Mock(" in src:
                if not any(kw in src for kw in [
                    "assert_called", "assert_not_called", "call_args",
                    "call_count", "called", "assert_any_call",
                ]):
                    issues.append(Issue(
                        rule_id=self.id,
                        rule_type=self.type,
                        severity=self.default_severity,
                        file=ctx.relative_path,
                        line=func.lineno,
                        message=f"Test `{func.name}` creates Mock without verifying calls",
                        recommendation="Add assert_called* or check call_args",
                    ))
        return issues


class PatchStartWithoutStop(Rule):
    id = "TQA021"
    type = "mocks"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            src = _func_source(func, ctx.lines)
            if ".start()" in src and "patch" in src:
                if ".stop()" not in src and "addCleanup" not in src:
                    issues.append(Issue(
                        rule_id=self.id,
                        rule_type=self.type,
                        severity=self.default_severity,
                        file=ctx.relative_path,
                        line=func.lineno,
                        message=f"Test `{func.name}` calls patcher.start() without stop()",
                        recommendation="Use context manager or call stop()/addCleanup",
                    ))
        return issues


class MonkeypatchAfterCall(Rule):
    id = "TQA022"
    type = "mocks"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        # Heuristic: find monkeypatch.setattr after a function call that looks like SUT invocation
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            stmts = func.body
            found_call = False
            for stmt in stmts:
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    found_call = True
                if found_call and isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    call = stmt.value
                    if isinstance(call.func, ast.Attribute) and call.func.attr == "setattr":
                        if (
                            isinstance(call.func.value, ast.Name)
                            and call.func.value.id == "monkeypatch"
                        ):
                            issues.append(Issue(
                                rule_id=self.id,
                                rule_type=self.type,
                                severity=self.default_severity,
                                file=ctx.relative_path,
                                line=stmt.lineno,
                                message="monkeypatch.setattr after tested call may have no effect",
                                recommendation="Move monkeypatch setup before the tested call",
                            ))
        return issues


# ---------------------------------------------------------------------------
# Generic Rules: Duplicates
# ---------------------------------------------------------------------------


def _normalize_ast_block(source: str) -> str:
    """Normalize variable names and literals for duplicate detection."""
    normalized = re.sub(r'"[^"]*"', '"STR"', source)
    normalized = re.sub(r"'[^']*'", "'STR'", normalized)
    normalized = re.sub(r"\b\d+\b", "NUM", normalized)
    normalized = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "UUID",
        normalized,
    )
    return normalized


class DuplicateSetup(Rule):
    id = "TQA030"
    type = "duplicates"
    default_severity = Severity.INFO

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        funcs = _get_test_functions(ctx.tree)
        setups: list[tuple[int, str]] = []

        for func in funcs:
            # Extract setup lines (before first assert)
            setup_lines: list[str] = []
            for stmt in func.body:
                if isinstance(stmt, ast.Assert):
                    break
                start = (stmt.lineno - 1) if stmt.lineno else 0
                end = (stmt.end_lineno or stmt.lineno)
                setup_lines.extend(ctx.lines[start:end])
            if len(setup_lines) >= config.duplicate_min_lines:
                normalized = _normalize_ast_block("\n".join(setup_lines))
                setups.append((func.lineno, normalized))

        # Find duplicates
        seen: dict[str, int] = {}
        for lineno, block in setups:
            if block in seen:
                issues.append(Issue(
                    rule_id=self.id,
                    rule_type=self.type,
                    severity=self.default_severity,
                    file=ctx.relative_path,
                    line=lineno,
                    message="Duplicate test setup pattern detected",
                    recommendation="Extract into shared fixture or helper function",
                ))
            else:
                seen[block] = lineno
        return issues


class DuplicateAssertionPattern(Rule):
    id = "TQA031"
    type = "duplicates"
    default_severity = Severity.INFO

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        funcs = _get_test_functions(ctx.tree)
        patterns: list[tuple[int, str, str]] = []

        for func in funcs:
            asserts: list[str] = []
            for node in ast.walk(func):
                if isinstance(node, ast.Assert):
                    start = (node.lineno - 1) if node.lineno else 0
                    end = node.end_lineno or node.lineno
                    asserts.extend(ctx.lines[start:end])
            if len(asserts) >= config.duplicate_min_lines:
                normalized = _normalize_ast_block("\n".join(asserts))
                patterns.append((func.lineno, func.name, normalized))

        seen: dict[str, tuple[int, str]] = {}
        for lineno, name, block in patterns:
            if block in seen:
                issues.append(Issue(
                    rule_id=self.id,
                    rule_type=self.type,
                    severity=self.default_severity,
                    file=ctx.relative_path,
                    line=lineno,
                    message=(
                        f"Test `{name}` has duplicate assertion pattern"
                        f" (also at line {seen[block][0]})"
                    ),
                    recommendation="Extract assertion helper or parametrize",
                ))
            else:
                seen[block] = (lineno, name)
        return issues


# ---------------------------------------------------------------------------
# Generic Rules: Edge cases
# ---------------------------------------------------------------------------


class MissingEdgeCase(Rule):
    id = "TQA040"
    type = "edge_cases"
    default_severity = Severity.INFO

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        # Heuristic: test file with only happy-path tests (no error/boundary checks)
        issues: list[Issue] = []
        funcs = _get_test_functions(ctx.tree)
        if not funcs:
            return issues

        has_error_test = any(
            "error" in f.name or "fail" in f.name or "reject" in f.name
            or "invalid" in f.name or "exceed" in f.name or "deny" in f.name
            for f in funcs
        )
        has_raises = any("pytest.raises" in _func_source(f, ctx.lines) for f in funcs)

        if not has_error_test and not has_raises and len(funcs) >= 3:
            issues.append(Issue(
                rule_id=self.id,
                rule_type=self.type,
                severity=self.default_severity,
                file=ctx.relative_path,
                line=1,
                message="Test file has no error/boundary/deny tests",
                recommendation="Add tests for error paths, edge cases, or invalid input",
            ))
        return issues


# ---------------------------------------------------------------------------
# Project-specific Rules: StylistTG
# ---------------------------------------------------------------------------


class DependencyOverridesWithoutFinally(Rule):
    id = "STG001"
    type = "project"
    default_severity = Severity.CRITICAL

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            src = _func_source(func, ctx.lines)
            if "dependency_overrides" in src and "dependency_overrides[" in src:
                if "finally" not in src and "app_client" not in src:
                    issues.append(Issue(
                        rule_id=self.id,
                        rule_type=self.type,
                        severity=self.default_severity,
                        file=ctx.relative_path,
                        line=func.lineno,
                        message=(
                            f"Test `{func.name}` modifies dependency_overrides"
                            " without finally/app_client"
                        ),
                        recommendation="Wrap in try/finally or use app_client context manager",
                    ))
        return issues


class TestClientWithoutAppClient(Rule):
    id = "STG002"
    type = "project"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            src = _func_source(func, ctx.lines)
            if "TestClient(app)" in src and "dependency_overrides" in src:
                if "app_client" not in src:
                    issues.append(Issue(
                        rule_id=self.id,
                        rule_type=self.type,
                        severity=self.default_severity,
                        file=ctx.relative_path,
                        line=func.lineno,
                        message=(
                            f"Test `{func.name}` uses TestClient(app)"
                            " + DB override without app_client"
                        ),
                        recommendation="Use app_client context manager for automatic cleanup",
                    ))
        return issues


class API4xxWithoutErrorCode(Rule):
    id = "STG003"
    type = "project"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            src = _func_source(func, ctx.lines)
            # Check for 4xx status code assertions
            four_xx = re.findall(r"status_code\s*==\s*(4\d{2})", src)
            if four_xx:
                if "error_code" not in src and ".json()" not in src:
                    issues.append(Issue(
                        rule_id=self.id,
                        rule_type=self.type,
                        severity=self.default_severity,
                        file=ctx.relative_path,
                        line=func.lineno,
                        message=f"Test `{func.name}` asserts 4xx without checking error body",
                        recommendation="Assert response.json() error_code or detail field",
                    ))
        return issues


class AmbiguousStatusCode(Rule):
    id = "STG004"
    type = "project"
    default_severity = Severity.INFO

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            src = _func_source(func, ctx.lines)
            if re.search(r"status_code\s+in\s+\{", src) or re.search(r"status_code\s+in\s+\[", src):
                if "# contract:" not in src and "# expected:" not in src:
                    issues.append(Issue(
                        rule_id=self.id,
                        rule_type=self.type,
                        severity=self.default_severity,
                        file=ctx.relative_path,
                        line=func.lineno,
                        message=(
                            f"Test `{func.name}` uses status_code in"
                            " {...} without contract comment"
                        ),
                        recommendation="Add # contract: comment explaining valid status codes",
                    ))
        return issues


class LiveTestWithoutEnvGuard(Rule):
    id = "STG005"
    type = "project"
    default_severity = Severity.CRITICAL

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            is_live = _has_marker(func, "live") or _has_marker(func, "integration")
            if is_live:
                src = _func_source(func, ctx.lines)
                has_skip = "pytest.skip" in src or "skipIf" in src or "skipUnless" in src
                has_env_check = "os.getenv" in src or "os.environ" in src
                if not has_skip and not has_env_check:
                    issues.append(Issue(
                        rule_id=self.id,
                        rule_type=self.type,
                        severity=self.default_severity,
                        file=ctx.relative_path,
                        line=func.lineno,
                        message=(
                            f"Live/integration test `{func.name}`"
                            " without env guard/pytest.skip"
                        ),
                        recommendation="Add env check + pytest.skip for missing credentials",
                    ))
        return issues


class S3StubberWithoutContext(Rule):
    id = "STG006"
    type = "project"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            src = _func_source(func, ctx.lines)
            if "Stubber(" in src or "stubber" in src:
                if "with stubber" not in src.lower() and "with Stubber" not in src:
                    # Check for `with stubber:` pattern
                    if "with stubber:" not in src:
                        issues.append(Issue(
                            rule_id=self.id,
                            rule_type=self.type,
                            severity=self.default_severity,
                            file=ctx.relative_path,
                            line=func.lineno,
                            message=f"Test `{func.name}` uses S3 Stubber without context manager",
                            recommendation="Use `with stubber:` context manager",
                        ))
        return issues


class RateLimitWithoutExceededCase(Rule):
    id = "STG007"
    type = "project"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        src = ctx.source
        if "FakeRedis" in src or "rate_limit" in src.lower():
            funcs = _get_test_functions(ctx.tree)
            has_exceeded = any(
                "exceeded" in f.name or "denied" in f.name or "over" in f.name
                or "exceeded" in _func_source(f, ctx.lines).lower()
                for f in funcs
            )
            if not has_exceeded and funcs:
                issues.append(Issue(
                    rule_id=self.id,
                    rule_type=self.type,
                    severity=self.default_severity,
                    file=ctx.relative_path,
                    line=1,
                    message="Rate-limit test file lacks exceeded/deny case",
                    recommendation="Add test for count > limit scenario",
                ))
        return issues


class RBACRouteNotInMatrix(Rule):
    id = "STG008"
    type = "project"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        # Only applicable to RBAC test files
        if "ENDPOINT_MATRIX" not in ctx.source:
            return []
        # This rule is mostly a reminder; actual completeness requires route introspection
        return []


class RuntimeRandomSecret(Rule):
    id = "STG009"
    type = "project"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            src = _func_source(func, ctx.lines)
            if "Fernet.generate_key()" in src:
                issues.append(Issue(
                    rule_id=self.id,
                    rule_type=self.type,
                    severity=self.default_severity,
                    file=ctx.relative_path,
                    line=func.lineno,
                    message=f"Test `{func.name}` generates runtime-random secret",
                    recommendation="Use fixed test constant for deterministic results",
                ))
        return issues


class LiveMarkerWithoutEnvSkip(Rule):
    id = "STG010"
    type = "project"
    default_severity = Severity.CRITICAL

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        # Same logic as STG005 but specifically for @pytest.mark.live
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            if _has_marker(func, "live"):
                src = _func_source(func, ctx.lines)
                has_skip = "pytest.skip" in src or "skipIf" in src
                has_env = "os.getenv" in src or "os.environ" in src
                if not has_skip and not has_env:
                    issues.append(Issue(
                        rule_id=self.id,
                        rule_type=self.type,
                        severity=self.default_severity,
                        file=ctx.relative_path,
                        line=func.lineno,
                        message=f"@pytest.mark.live test `{func.name}` without required env skip",
                        recommendation="Add os.getenv() check + pytest.skip()",
                    ))
        return issues


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------


ALL_RULES: list[Rule] = [
    # Assertions
    ZeroAssertions(),
    AssertTrue(),
    AssertSelfEquality(),
    TooManyAssertions(),
    UnittestAssertTrue(),
    ManualExceptionCatch(),
    # Flaky
    TimeSleep(),
    RandomWithoutSeed(),
    DatetimeNow(),
    ExternalHTTPWithoutMarker(),
    FilesystemWriteOutsideTmp(),
    # Mocks
    MockWithoutAssert(),
    PatchStartWithoutStop(),
    MonkeypatchAfterCall(),
    # Duplicates
    DuplicateSetup(),
    DuplicateAssertionPattern(),
    # Edge cases
    MissingEdgeCase(),
    # Project-specific
    DependencyOverridesWithoutFinally(),
    TestClientWithoutAppClient(),
    API4xxWithoutErrorCode(),
    AmbiguousStatusCode(),
    LiveTestWithoutEnvGuard(),
    S3StubberWithoutContext(),
    RateLimitWithoutExceededCase(),
    RBACRouteNotInMatrix(),
    RuntimeRandomSecret(),
    LiveMarkerWithoutEnvSkip(),
]


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


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
        except (UnicodeDecodeError, OSError):
            return []

        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []

        lines = source.splitlines()
        relative_path = str(path.relative_to(base_dir)).replace("\\", "/")

        line_supprs, file_supprs, supp_warnings = _parse_suppressions(lines, relative_path)

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

        all_issues: list[Issue] = list(supp_warnings)

        for rule in self.rules:
            try:
                issues = rule.check(ctx, self.config)
            except Exception:
                continue
            for issue in issues:
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

        # Coverage-driven warnings for source files with uncovered branches
        if self.coverage_data:
            all_issues.extend(self._coverage_branch_warnings())

        return all_issues

    def _coverage_branch_warnings(self) -> list[Issue]:
        issues: list[Issue] = []
        files = self.coverage_data.get("files", {}) if self.coverage_data else {}
        for filepath, info in files.items():
            summary = info.get("summary", {})
            num_branches = summary.get("num_branches", 0)
            covered_branches = summary.get("covered_branches", 0)
            if num_branches > 0 and covered_branches < num_branches:
                missing = num_branches - covered_branches
                pct = round(covered_branches / num_branches * 100, 1)
                issues.append(Issue(
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
                ))
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
# Reporters
# ---------------------------------------------------------------------------


class TextReporter:
    def report(self, issues: list[Issue]) -> str:
        lines: list[str] = []
        for issue in issues:
            sev = issue.severity.name
            lines.append(
                f"[{sev}] {issue.file}:{issue.line} | {issue.rule_id} | "
                f"{issue.rule_type} | {issue.message} \u2192 {issue.recommendation}"
            )
        return "\n".join(lines)


class JsonReporter:
    def report(self, issues: list[Issue]) -> str:
        by_severity: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_file: dict[str, int] = {}
        for issue in issues:
            sev = issue.severity.name
            by_severity[sev] = by_severity.get(sev, 0) + 1
            by_type[issue.rule_type] = by_type.get(issue.rule_type, 0) + 1
            by_file[issue.file] = by_file.get(issue.file, 0) + 1

        data: dict[str, Any] = {
            "summary": {
                "total": len(issues),
                "by_severity": by_severity,
                "by_type": by_type,
                "by_file": by_file,
            },
            "issues": [
                {
                    "rule_id": i.rule_id,
                    "rule_type": i.rule_type,
                    "severity": i.severity.name,
                    "file": i.file,
                    "line": i.line,
                    "message": i.message,
                    "recommendation": i.recommendation,
                    "fingerprint": i.fingerprint(),
                }
                for i in issues
            ],
        }
        return json.dumps(data, indent=2)


class SarifReporter:
    SARIF_VERSION = "2.1.0"
    SCHEMA_URI = "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"

    def report(self, issues: list[Issue]) -> str:
        rules_map: dict[str, dict[str, Any]] = {}
        results: list[dict[str, Any]] = []

        for issue in issues:
            if issue.rule_id not in rules_map:
                rules_map[issue.rule_id] = {
                    "id": issue.rule_id,
                    "shortDescription": {"text": f"[{issue.rule_type}] {issue.rule_id}"},
                    "defaultConfiguration": {
                        "level": self._severity_to_level(issue.severity)
                    },
                }

            results.append({
                "ruleId": issue.rule_id,
                "level": self._severity_to_level(issue.severity),
                "message": {"text": f"{issue.message} \u2192 {issue.recommendation}"},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": issue.file},
                            "region": {"startLine": issue.line},
                        }
                    }
                ],
                "fingerprints": {"primaryLocationLineHash": issue.fingerprint()},
            })

        sarif: dict[str, Any] = {
            "$schema": self.SCHEMA_URI,
            "version": self.SARIF_VERSION,
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "test-quality-analyzer",
                            "version": "1.0.0",
                            "informationUri": "https://github.com/pinnnthreetriples/StylistTG",
                            "rules": list(rules_map.values()),
                        }
                    },
                    "results": results,
                }
            ],
        }
        return json.dumps(sarif, indent=2)

    @staticmethod
    def _severity_to_level(severity: Severity) -> str:
        if severity == Severity.CRITICAL:
            return "error"
        elif severity == Severity.WARNING:
            return "warning"
        return "note"


# ---------------------------------------------------------------------------
# Coverage integration
# ---------------------------------------------------------------------------


def load_coverage_context(coverage_path: Path) -> dict[str, Any] | None:
    if not coverage_path.exists():
        return None
    try:
        return json.loads(coverage_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="test-quality-analyzer",
        description="Static test quality analyzer for pytest suites",
    )
    parser.add_argument("--path", required=True, help="Path to test file or directory")
    parser.add_argument(
        "--format", choices=["text", "json", "sarif"], default="text", help="Output format"
    )
    parser.add_argument("--output", help="Output file path (stdout if omitted)")
    parser.add_argument(
        "--severity",
        choices=["INFO", "WARNING", "CRITICAL"],
        default="INFO",
        help="Minimum severity to report",
    )
    parser.add_argument("--baseline", help="Path to baseline JSON file")
    parser.add_argument("--config", help="Path to test-quality.toml config")
    parser.add_argument("--coverage", help="Path to coverage JSON report")

    args = parser.parse_args(argv)

    # Load config
    config_path = Path(args.config) if args.config else Path("test-quality.toml")
    if config_path.exists():
        config = AnalyzerConfig.from_toml(config_path)
    else:
        config = AnalyzerConfig()

    # Resolve path
    target = Path(args.path)
    if not target.exists():
        print(f"Error: path '{args.path}' does not exist", file=sys.stderr)
        return 2

    # Base directory for relative paths
    base_dir = target if target.is_dir() else target.parent

    # Load coverage data
    coverage_data = None
    if args.coverage:
        coverage_data = load_coverage_context(Path(args.coverage))

    # Run analysis
    analyzer = Analyzer(config, coverage_data=coverage_data)
    try:
        issues = analyzer.analyze(target, base_dir)
    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        return 2

    # Filter by severity
    min_severity = Severity.from_str(args.severity)
    issues = [i for i in issues if i.severity >= min_severity]

    # Apply baseline
    if args.baseline:
        baseline = load_baseline(Path(args.baseline))
        issues = filter_by_baseline(issues, baseline)

    # Report
    reporters = {
        "text": TextReporter(),
        "json": JsonReporter(),
        "sarif": SarifReporter(),
    }
    reporter = reporters[args.format]
    output = reporter.report(issues)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
    else:
        print(output)

    # Exit code
    has_critical = any(i.severity == Severity.CRITICAL for i in issues)
    return 1 if has_critical else 0


if __name__ == "__main__":
    sys.exit(main())
