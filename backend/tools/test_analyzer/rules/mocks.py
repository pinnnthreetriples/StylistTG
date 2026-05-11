"""Mock/patch quality rules (TQA020–TQA022)."""
from __future__ import annotations

import ast

from ..models import (
    AnalyzerConfig,
    FileContext,
    Issue,
    Rule,
    Severity,
    _func_source,
    _get_test_functions,
)


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
