"""AST-based detectors for weak HTTP-response assertions (issue #270).

These rules complement the older string-based checks by inspecting the
parsed syntax tree, which avoids false positives from comments / strings
that mention the same pattern. They target patterns explicitly listed as
"prohibited" by the strict assertion policy in
``docs/quality/QUALITY_GATES.md``.

- :class:`AssertResponseJsonTruthiness` — flags ``assert response.json()``
  as a truthiness check (TQA050).
- :class:`AssertKeyInResponseJson` — flags ``assert "detail" in
  response.json()`` style patterns (TQA051).
"""

from __future__ import annotations

import ast

from ..models import AnalyzerConfig, FileContext, Issue, Rule, Severity, get_test_functions


def _calls_response_json(node: ast.AST) -> bool:
    """Return True if ``node`` is a ``<something>.json()`` call (no args)."""
    return (
        isinstance(node, ast.Call)
        and not node.args
        and not node.keywords
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "json"
    )


def _calls_response_json_get(node: ast.AST) -> bool:
    """Return True if ``node`` is ``<something>.json().get(...)``.

    Without this helper, TQA051 silently passes the weak idiom
    ``assert "x" in response.json().get("detail", "")`` even though the
    rule's docstring claims it catches both forms. The narrow shape check
    (attribute chain ``.json()`` → ``.get``) avoids flagging plain
    ``dict.get`` membership probes elsewhere.
    """
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and _calls_response_json(node.func.value)
    )


class AssertResponseJsonTruthiness(Rule):
    id = "TQA050"
    type = "assertions"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in get_test_functions(ctx.tree):
            for node in ast.walk(func):
                if not isinstance(node, ast.Assert):
                    continue
                test = node.test
                # `assert response.json()`  (truthiness — any non-empty dict passes)
                if _calls_response_json(test):
                    issues.append(
                        Issue(
                            rule_id=self.id,
                            rule_type=self.type,
                            severity=self.default_severity,
                            file=ctx.relative_path,
                            line=node.lineno,
                            message=(
                                "`assert response.json()` only checks truthiness; "
                                "assert the exact body shape or error envelope instead."
                            ),
                            recommendation=(
                                "Use tests.helpers.assertions.assert_error_response or "
                                "assert response.json() == {expected exact dict}."
                            ),
                        )
                    )
        return issues


class AssertKeyInResponseJson(Rule):
    id = "TQA051"
    type = "assertions"
    default_severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        issues: list[Issue] = []
        for func in get_test_functions(ctx.tree):
            for node in ast.walk(func):
                if not isinstance(node, ast.Assert):
                    continue
                # Match `assert <const> in <something>.json()` and
                # `assert <const> in <something>.json().get(...)` — both
                # are key-membership probes that don't pin the value.
                test = node.test
                if (
                    isinstance(test, ast.Compare)
                    and len(test.ops) == 1
                    and isinstance(test.ops[0], ast.In)
                    and isinstance(test.left, ast.Constant)
                    and isinstance(test.left.value, str)
                    and (
                        _calls_response_json(test.comparators[0])
                        or _calls_response_json_get(test.comparators[0])
                    )
                ):
                    issues.append(
                        Issue(
                            rule_id=self.id,
                            rule_type=self.type,
                            severity=self.default_severity,
                            file=ctx.relative_path,
                            line=node.lineno,
                            message=(
                                f'`assert "{test.left.value}" in response.json()` only '
                                "asserts a key exists; assert the exact value or use "
                                "assert_error_response."
                            ),
                            recommendation=(
                                "Use response.json()[key] == expected_value or "
                                "tests.helpers.assertions.assert_error_response."
                            ),
                        )
                    )
        return issues
