"""Bad/good sample tests for the AST-based weak-response rules (issue #270)."""

# test-analyzer: disable-file=TQA040 reason="rule-testing fixtures, not behaviour tests"

from __future__ import annotations

import ast

import pytest

from tools.test_analyzer.models import AnalyzerConfig, FileContext
from tools.test_analyzer.rules.weak_response import (
    AssertKeyInResponseJson,
    AssertResponseJsonTruthiness,
)

pytestmark = pytest.mark.unit


def _ctx(source: str) -> FileContext:
    return FileContext(
        path=None,  # type: ignore[arg-type]
        relative_path="tests/sample.py",
        source=source,
        tree=ast.parse(source),
        lines=source.splitlines(),
        suppressions={},
        file_suppressions=set(),
        suppression_warnings=[],
    )


def _config() -> AnalyzerConfig:
    return AnalyzerConfig()


# ---- TQA050: assert response.json() truthiness ------------------------------


def test_truthiness_rule_flags_bare_response_json_assertion() -> None:
    source = "def test_thing():\n    response = call()\n    assert response.json()\n"
    issues = AssertResponseJsonTruthiness().check(_ctx(source), _config())
    assert len(issues) == 1
    assert issues[0].rule_id == "TQA050"
    assert issues[0].line == 3


def test_truthiness_rule_ignores_exact_equality_assertion() -> None:
    source = (
        "def test_thing():\n"
        "    response = call()\n"
        "    assert response.json() == {'error_code': 'X'}\n"
    )
    issues = AssertResponseJsonTruthiness().check(_ctx(source), _config())
    assert issues == []


def test_truthiness_rule_ignores_assertion_outside_test_function() -> None:
    source = "def helper():\n    response = call()\n    assert response.json()\n"
    issues = AssertResponseJsonTruthiness().check(_ctx(source), _config())
    assert issues == []


# ---- TQA051: assert "X" in response.json() ----------------------------------


def test_key_in_rule_flags_key_membership_check() -> None:
    source = 'def test_thing():\n    response = call()\n    assert "detail" in response.json()\n'
    issues = AssertKeyInResponseJson().check(_ctx(source), _config())
    assert len(issues) == 1
    assert issues[0].rule_id == "TQA051"
    assert "detail" in issues[0].message


def test_key_in_rule_ignores_exact_value_assertion() -> None:
    source = (
        "def test_thing():\n"
        "    response = call()\n"
        '    assert response.json()["detail"] == "missing token"\n'
    )
    issues = AssertKeyInResponseJson().check(_ctx(source), _config())
    assert issues == []


def test_key_in_rule_ignores_membership_against_non_json_call() -> None:
    source = 'def test_thing():\n    seen = set()\n    assert "item" in seen\n'
    issues = AssertKeyInResponseJson().check(_ctx(source), _config())
    assert issues == []
