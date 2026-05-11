"""Static test quality analyzer for pytest/unittest suites.

Examples:
    python -m tools.test_analyzer --path tests
    python -m tools.test_analyzer --path tests --format sarif --output reports/test-quality.sarif
    python -m tools.test_analyzer --explain STG001

Exit codes:
    0: no CRITICAL issues
    1: CRITICAL issues found
    2: CLI/analyzer error
"""
from .analyzer import Analyzer, filter_by_baseline, load_baseline, load_coverage_context
from .cli import main
from .models import AnalyzerConfig, FileContext, Issue, Rule, Severity
from .reporters import JsonReporter, SarifReporter, TextReporter
from .rules import ALL_RULES

__all__ = [
    "ALL_RULES",
    "Analyzer",
    "AnalyzerConfig",
    "FileContext",
    "Issue",
    "JsonReporter",
    "Rule",
    "SarifReporter",
    "Severity",
    "TextReporter",
    "filter_by_baseline",
    "load_baseline",
    "load_coverage_context",
    "main",
]
