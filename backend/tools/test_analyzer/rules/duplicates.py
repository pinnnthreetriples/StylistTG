"""Duplicate code detection rules (TQA030–TQA031)."""

from __future__ import annotations

import ast

from ..models import (
    AnalyzerConfig,
    FileContext,
    Issue,
    Rule,
    Severity,
    get_test_functions,
    normalize_ast_block,
)


class DuplicateSetup(Rule):
    id = "TQA030"
    type = "duplicates"
    default_severity = Severity.INFO

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        funcs = get_test_functions(ctx.tree)
        setups: list[tuple[int, str]] = []

        for func in funcs:
            setup_lines: list[str] = []
            for stmt in func.body:
                if isinstance(stmt, ast.Assert):
                    break
                start = (stmt.lineno - 1) if stmt.lineno else 0
                end = stmt.end_lineno or stmt.lineno
                setup_lines.extend(ctx.lines[start:end])
            if len(setup_lines) >= config.duplicate_min_lines:
                normalized = normalize_ast_block("\n".join(setup_lines))
                setups.append((func.lineno, normalized))

        seen: dict[str, int] = {}
        for lineno, block in setups:
            if block in seen:
                issues.append(
                    Issue(
                        rule_id=self.id,
                        rule_type=self.type,
                        severity=self.default_severity,
                        file=ctx.relative_path,
                        line=lineno,
                        message="Duplicate test setup pattern detected",
                        recommendation="Extract into shared fixture or helper function",
                    )
                )
            else:
                seen[block] = lineno
        return issues


class DuplicateAssertionPattern(Rule):
    id = "TQA031"
    type = "duplicates"
    default_severity = Severity.INFO

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        funcs = get_test_functions(ctx.tree)
        patterns: list[tuple[int, str, str]] = []

        for func in funcs:
            asserts: list[str] = []
            for node in ast.walk(func):
                if isinstance(node, ast.Assert):
                    start = (node.lineno - 1) if node.lineno else 0
                    end = node.end_lineno or node.lineno
                    asserts.extend(ctx.lines[start:end])
            if len(asserts) >= config.duplicate_min_lines:
                normalized = normalize_ast_block("\n".join(asserts))
                patterns.append((func.lineno, func.name, normalized))

        seen: dict[str, tuple[int, str]] = {}
        for lineno, name, block in patterns:
            if block in seen:
                issues.append(
                    Issue(
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
                    )
                )
            else:
                seen[block] = (lineno, name)
        return issues
