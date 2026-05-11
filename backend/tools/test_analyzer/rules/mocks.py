"""Mock/patch quality rules (TQA020–TQA022)."""

from __future__ import annotations

import ast
import re

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
                if not any(
                    kw in src
                    for kw in [
                        "assert_called",
                        "assert_not_called",
                        "call_args",
                        "call_count",
                        "called",
                        "assert_any_call",
                    ]
                ):
                    issues.append(
                        Issue(
                            rule_id=self.id,
                            rule_type=self.type,
                            severity=self.default_severity,
                            file=ctx.relative_path,
                            line=func.lineno,
                            message=f"Test `{func.name}` creates Mock without verifying calls",
                            recommendation="Add assert_called* or check call_args",
                        )
                    )
        return issues


class PatchStartWithoutStop(Rule):
    id = "TQA021"
    type = "mocks"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            src = _func_source(func, ctx.lines)
            # Match actual patch() calls — not pytest's `monkeypatch` fixture
            # or unrelated `.start()` calls (e.g. threading.Thread.start()).
            has_patch_call = "patch(" in src or "patch.object(" in src
            has_patcher_start = re.search(r"\bpatcher\b.*\.start\(\)", src, re.DOTALL) is not None
            if has_patcher_start or (has_patch_call and ".start()" in src):
                if ".stop()" not in src and "addCleanup" not in src and "with patch" not in src:
                    issues.append(
                        Issue(
                            rule_id=self.id,
                            rule_type=self.type,
                            severity=self.default_severity,
                            file=ctx.relative_path,
                            line=func.lineno,
                            message=f"Test `{func.name}` calls patcher.start() without stop()",
                            recommendation="Use context manager or call stop()/addCleanup",
                        )
                    )
        return issues


class MonkeypatchAfterCall(Rule):
    id = "TQA022"
    type = "mocks"
    default_severity = Severity.WARNING

    _MONKEYPATCH_METHODS = frozenset(
        {
            "setattr",
            "delattr",
            "setitem",
            "delitem",
            "setenv",
            "delenv",
        }
    )

    @classmethod
    def _is_monkeypatch_call(cls, call: ast.Call) -> bool:
        """Return True if *call* is monkeypatch.<method>(...)."""
        return (
            isinstance(call.func, ast.Attribute)
            and call.func.attr in cls._MONKEYPATCH_METHODS
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "monkeypatch"
        )

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in _get_test_functions(ctx.tree):
            found_assert = False
            for stmt in func.body:
                if isinstance(stmt, ast.Assert):
                    found_assert = True
                if (
                    found_assert
                    and isinstance(stmt, ast.Expr)
                    and isinstance(stmt.value, ast.Call)
                    and self._is_monkeypatch_call(stmt.value)
                ):
                    issues.append(
                        Issue(
                            rule_id=self.id,
                            rule_type=self.type,
                            severity=self.default_severity,
                            file=ctx.relative_path,
                            line=stmt.lineno,
                            message=(
                                "monkeypatch.setattr after assert —"
                                " setup has no effect on tested code"
                            ),
                            recommendation="Move monkeypatch setup before the tested call",
                        )
                    )
        return issues
