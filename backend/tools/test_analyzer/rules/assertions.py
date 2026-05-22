"""Assertion quality rules (TQA001–TQA006)."""

from __future__ import annotations

import ast

from ..models import (
    AnalyzerConfig,
    FileContext,
    FunctionNode,
    Issue,
    Rule,
    Severity,
    count_asserts,
    func_source,
    get_test_functions,
)


_TQA007_SCOPE_MARKERS = {"unit", "security"}


class ZeroAssertions(Rule):
    id = "TQA001"
    type = "assertions"
    default_severity = Severity.CRITICAL

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in get_test_functions(ctx.tree):
            if count_asserts(func) == 0:
                src = func_source(func, ctx.lines)
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
        for func in get_test_functions(ctx.tree):
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
        for func in get_test_functions(ctx.tree):
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
        for func in get_test_functions(ctx.tree):
            count = count_asserts(func)
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
        for func in get_test_functions(ctx.tree):
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
        for func in get_test_functions(ctx.tree):
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


class PytestRaisesWithoutMatch(Rule):
    id = "TQA007"
    type = "assertions"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in get_test_functions(ctx.tree):
            if not _is_unit_or_security_test(ctx, func):
                continue
            for node in ast.walk(func):
                if isinstance(node, ast.Call) and _is_pytest_raises_call(node):
                    if not any(keyword.arg == "match" for keyword in node.keywords):
                        issues.append(
                            Issue(
                                rule_id=self.id,
                                rule_type=self.type,
                                severity=self.default_severity,
                                file=ctx.relative_path,
                                line=node.lineno,
                                message="pytest.raises() in unit/security test lacks match=",
                                recommendation=(
                                    "Add match= to verify the expected exception message"
                                ),
                            )
                        )
        return issues


class BroadExcept(Rule):
    id = "TQA008"
    type = "assertions"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in get_test_functions(ctx.tree):
            for node in ast.walk(func):
                if isinstance(node, ast.Try):
                    for handler in node.handlers:
                        if _is_broad_except(handler.type):
                            issues.append(
                                Issue(
                                    rule_id=self.id,
                                    rule_type=self.type,
                                    severity=self.default_severity,
                                    file=ctx.relative_path,
                                    line=handler.lineno,
                                    message="Test uses broad or bare except",
                                    recommendation="Catch the specific exception type under test",
                                )
                            )
        return issues


def _is_unit_or_security_test(ctx: FileContext, func: FunctionNode) -> bool:
    if (
        _decorators_have_scope_marker(func.decorator_list)
        or _enclosing_class_has_scope_marker(ctx.tree, func)
        or _module_has_scope_marker(ctx.tree)
    ):
        return True

    return _path_is_unit_or_security(ctx.relative_path)


def _path_is_unit_or_security(relative_path: str) -> bool:
    path = relative_path.lower().replace("\\", "/")
    parts = path.split("/")
    filename = parts[-1] if parts else path
    return (
        "unit" in parts
        or "security" in parts
        or filename.startswith("test_security")
        or filename.startswith("security_")
    )


def _decorators_have_scope_marker(decorators: list[ast.expr]) -> bool:
    return any(_expr_has_scope_marker(decorator) for decorator in decorators)


def _enclosing_class_has_scope_marker(tree: ast.AST, func: FunctionNode) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not _decorators_have_scope_marker(node.decorator_list):
            continue
        if any(child is func for child in ast.walk(node)):
            return True
    return False


def _module_has_scope_marker(tree: ast.AST) -> bool:
    if not isinstance(tree, ast.Module):
        return False

    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            if any(_is_pytestmark_target(target) for target in stmt.targets):
                if _expr_has_scope_marker(stmt.value):
                    return True
        elif isinstance(stmt, ast.AnnAssign) and _is_pytestmark_target(stmt.target):
            if _expr_has_scope_marker(stmt.value):
                return True
    return False


def _is_pytestmark_target(target: ast.expr) -> bool:
    return isinstance(target, ast.Name) and target.id == "pytestmark"


def _expr_has_scope_marker(expr: ast.AST | None) -> bool:
    if expr is None:
        return False
    if isinstance(expr, ast.Call):
        return _expr_has_scope_marker(expr.func)
    if isinstance(expr, (ast.List, ast.Tuple)):
        return any(_expr_has_scope_marker(elt) for elt in expr.elts)
    return _pytest_mark_name(expr) in _TQA007_SCOPE_MARKERS


def _pytest_mark_name(expr: ast.AST) -> str | None:
    if not isinstance(expr, ast.Attribute):
        return None
    if not _is_pytest_mark_namespace(expr.value):
        return None
    return expr.attr


def _is_pytest_mark_namespace(expr: ast.AST) -> bool:
    return (
        isinstance(expr, ast.Attribute)
        and expr.attr == "mark"
        and isinstance(expr.value, ast.Name)
        and expr.value.id == "pytest"
    )


def _is_pytest_raises_call(node: ast.Call) -> bool:
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "raises"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "pytest"
    )


def _is_broad_except(handler_type: ast.expr | None) -> bool:
    if handler_type is None:
        return True
    if isinstance(handler_type, ast.Name):
        return handler_type.id in {"Exception", "BaseException"}
    if isinstance(handler_type, ast.Tuple):
        return any(_is_broad_except(elt) for elt in handler_type.elts)
    return False
