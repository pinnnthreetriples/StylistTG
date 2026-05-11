"""Assertion quality rules (TQA001–TQA006)."""

from __future__ import annotations

import ast

from ..models import (
    AnalyzerConfig,
    FileContext,
    Issue,
    Rule,
    Severity,
    _count_asserts,
    _func_source,
    _get_test_functions,
)


class ZeroAssertions(Rule):
    id = "TQA001"
    type = "assertions"
    default_severity = Severity.CRITICAL

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            if _count_asserts(func) == 0:
                src = _func_source(func, ctx.lines)
                if "pytest.raises" not in src and "assertRaises" not in src:
                    issues.append(
                        Issue(
                            rule_id=self.id,
                            rule_type=self.type,
                            severity=self.default_severity,
                            file=ctx.relative_path,
                            line=func.lineno,
                            message=f"Test `{func.name}` has zero assertions",
                            recommendation="Add assert statements or use pytest.raises",
                        )
                    )
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
                        issues.append(
                            Issue(
                                rule_id=self.id,
                                rule_type=self.type,
                                severity=self.default_severity,
                                file=ctx.relative_path,
                                line=node.lineno,
                                message="`assert True` is a no-op assertion",
                                recommendation="Replace with a meaningful assertion",
                            )
                        )
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
                            issues.append(
                                Issue(
                                    rule_id=self.id,
                                    rule_type=self.type,
                                    severity=self.default_severity,
                                    file=ctx.relative_path,
                                    line=node.lineno,
                                    message="`assert x == x` is always true",
                                    recommendation="Compare against expected value",
                                )
                            )
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
                issues.append(
                    Issue(
                        rule_id=self.id,
                        rule_type=self.type,
                        severity=self.default_severity,
                        file=ctx.relative_path,
                        line=func.lineno,
                        message=f"Test `{func.name}` has {count} assertions (max {limit})",
                        recommendation="Split into focused tests or extract helper",
                    )
                )
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
                            issues.append(
                                Issue(
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
                                )
                            )
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
                        if node.orelse:
                            for stmt in node.orelse:
                                src = ast.dump(stmt)
                                if "pytest.fail" in src or (
                                    isinstance(stmt, ast.Assert)
                                    and isinstance(stmt.test, ast.Constant)
                                    and stmt.test.value is False
                                ):
                                    issues.append(
                                        Issue(
                                            rule_id=self.id,
                                            rule_type=self.type,
                                            severity=self.default_severity,
                                            file=ctx.relative_path,
                                            line=node.lineno,
                                            message="Manual try/except/else for expected exception",
                                            recommendation="Use pytest.raises() context manager",
                                        )
                                    )
                                    break
        return issues
