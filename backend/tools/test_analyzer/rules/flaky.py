"""Flaky/non-deterministic test rules (TQA010–TQA014)."""
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
    _has_marker,
)


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
