"""Edge case detection rules (TQA040)."""
from __future__ import annotations

import re

from ..models import (
    AnalyzerConfig,
    FileContext,
    Issue,
    Rule,
    Severity,
    _get_test_functions,
)

# Words in test names that indicate a negative/boundary/edge-case test.
_NEGATIVE_NAME_KEYWORDS = (
    "error", "fail", "reject", "invalid", "exceed", "deny",
    "block", "redact", "sanitize", "scoped", "requires", "missing",
    "without", "unauthorized", "forbidden", "expired", "conflict",
    "not_", "cannot", "absent", "empty", "limit", "cooldown",
    "uncertain", "timeout", "blocked", "denied", "404", "401", "403", "409", "422",
)

# Source-level patterns indicating boundary/error checks.
_NEGATIVE_SOURCE_RE = re.compile(
    r"pytest\.raises|"
    r"with\s+raises\(|"
    r"status_code\s*==\s*4\d{2}|"
    r"status_code\s+in\s+\{[^}]*4\d{2}"
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

        has_error_name = any(
            any(kw in f.name for kw in _NEGATIVE_NAME_KEYWORDS) for f in funcs
        )
        has_source_signal = bool(_NEGATIVE_SOURCE_RE.search(ctx.source))

        if not has_error_name and not has_source_signal and len(funcs) >= 3:
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
