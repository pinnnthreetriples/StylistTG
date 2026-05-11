"""StylistTG project-specific rules (STG001–STG010)."""
from __future__ import annotations

import re

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
            if (
                re.search(r"status_code\s+in\s+\{", src)
                or re.search(r"status_code\s+in\s+\[", src)
            ):
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
        if "ENDPOINT_MATRIX" not in ctx.source:
            return []
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
