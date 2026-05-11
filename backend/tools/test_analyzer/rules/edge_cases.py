"""Edge case detection rules (TQA040)."""
from __future__ import annotations

from ..models import (
    AnalyzerConfig,
    FileContext,
    Issue,
    Rule,
    Severity,
    _func_source,
    _get_test_functions,
)


class MissingEdgeCase(Rule):
    id = "TQA040"
    type = "edge_cases"
    default_severity = Severity.INFO

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
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
