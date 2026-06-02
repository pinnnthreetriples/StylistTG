"""Regression tests for the zero-warning / zero-soft-fail policy (issue #262).

These tests pin the strict-enforcement contract so future changes cannot silently
weaken the quality gate. They cover:

- analyzer CLI exits non-zero on INFO findings when ``--fail-on-severity INFO``;
- analyzer writes SARIF and JSON before exiting non-zero;
- ``backend/pyproject.toml`` registers every marker used in ``backend/tests``;
- ``backend/test-quality.toml`` has no enabled no-op rules (e.g. STG008);
- the test-quality CI workflow does not use ``continue-on-error: true`` on the
  required quality path.
"""

from __future__ import annotations

import ast
import json
import re
import sys
import tomllib
from pathlib import Path

import pytest

from tools.test_analyzer import main
from tools.test_analyzer.rules import ALL_RULES

pytestmark = pytest.mark.unit


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
TESTS_DIR = BACKEND_ROOT / "tests"
PYPROJECT = BACKEND_ROOT / "pyproject.toml"
TEST_QUALITY_TOML = BACKEND_ROOT / "test-quality.toml"
TEST_QUALITY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test-quality.yml"
NIGHTLY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "nightly-backend-quality.yml"


# ---- A. Analyzer CLI hard-fails on INFO --------------------------------------


def _write_info_finding_sample(path: Path) -> None:
    # TQA040 (info-severity) flags test functions with zero assertions per
    # backend/test-quality.toml. This is a deterministic INFO finding.
    path.write_text(
        "def test_zero_assertions():\n    x = 1\n    y = 2\n    _ = x + y\n",
        encoding="utf-8",
    )


def test_analyzer_cli_exits_nonzero_on_info(tmp_path: Path) -> None:
    sample = tmp_path / "test_zero_assert.py"
    _write_info_finding_sample(sample)
    report_dir = tmp_path / "reports"

    exit_code = main(
        [
            "--path",
            str(sample),
            "--format",
            "json,sarif",
            "--output-dir",
            str(report_dir),
            "--severity",
            "INFO",
            "--fail-on-severity",
            "INFO",
        ]
    )

    assert exit_code != 0, "analyzer must exit non-zero when INFO findings exist"


def test_analyzer_writes_reports_before_failing(tmp_path: Path) -> None:
    sample = tmp_path / "test_zero_assert.py"
    _write_info_finding_sample(sample)
    report_dir = tmp_path / "reports"

    main(
        [
            "--path",
            str(sample),
            "--format",
            "json,sarif",
            "--output-dir",
            str(report_dir),
            "--severity",
            "INFO",
            "--fail-on-severity",
            "INFO",
        ]
    )

    assert (report_dir / "test-quality.json").is_file()
    sarif = json.loads((report_dir / "test-quality.sarif").read_text(encoding="utf-8"))
    assert sarif["version"] == "2.1.0"


# ---- B. Pytest marker registration is complete -------------------------------


_MARK_DECORATOR = re.compile(r"@pytest\.mark\.(\w+)")
_PYTESTMARK_ATTR = re.compile(r"pytest\.mark\.(\w+)")
# Built-in / parametrize markers don't need to be registered.
_BUILTIN_MARKERS = {"parametrize", "skipif", "skip", "xfail", "filterwarnings", "usefixtures"}


def _registered_markers() -> set[str]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    markers_block = data["tool"]["pytest"]["ini_options"]["markers"]
    out: set[str] = set()
    for entry in markers_block:
        name = entry.split(":", 1)[0].strip()
        out.add(name)
    return out


def _collect_used_markers() -> set[str]:
    used: set[str] = set()
    for file in TESTS_DIR.rglob("*.py"):
        text = file.read_text(encoding="utf-8", errors="replace")
        used.update(_MARK_DECORATOR.findall(text))
        # Capture module-level pytestmark assignments.
        for line in text.splitlines():
            if "pytestmark" in line and "pytest.mark." in line:
                used.update(_PYTESTMARK_ATTR.findall(line))
    return used - _BUILTIN_MARKERS


def test_pyproject_markers_cover_all_pytestmark_usages() -> None:
    used = _collect_used_markers()
    registered = _registered_markers()
    missing = sorted(used - registered)
    assert not missing, (
        f"strict_markers requires every used marker to be registered in "
        f"backend/pyproject.toml [tool.pytest.ini_options].markers. "
        f"Missing: {missing}"
    )


def _is_broad_ignore(entry: str) -> bool:
    """Return True if a filterwarnings entry is a forbidden bare-category ignore.

    Pytest filter spec is ``action:message:category:module:lineno``. A bare
    ``ignore::ResourceWarning`` (or ``ignore::pytest.PytestUnraisableExceptionWarning``)
    matches every warning of that class in any module — including production
    paths the zero-warning policy must keep red. Each ``ignore`` MUST pin
    either a message regex (field 1) or a module regex (field 3).
    """
    if entry == "error" or not entry.startswith("ignore"):
        return False
    parts = entry.split(":")
    # action[0]  message[1]  category[2]  module[3]  lineno[4]
    message = parts[1] if len(parts) > 1 else ""
    module = parts[3] if len(parts) > 3 else ""
    return not message.strip() and not module.strip()


def test_pyproject_filterwarnings_forbids_broad_ignores() -> None:
    """The shipped pyproject.toml has no broad `ignore::Category` entry."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    entries = data["tool"]["pytest"]["ini_options"]["filterwarnings"]
    offenders = [entry for entry in entries if _is_broad_ignore(entry)]
    assert not offenders, (
        f"broad warning ignores forbidden — each `ignore` filter must pin "
        f"either a message regex (field 1) or a module regex (field 3). "
        f"Offending entries: {offenders}"
    )


@pytest.mark.parametrize(
    "broad_entry",
    [
        "ignore::ResourceWarning",
        "ignore::DeprecationWarning",
        "ignore::UserWarning",
        "ignore::pytest.PytestUnraisableExceptionWarning",
    ],
)
def test_broad_ignore_validator_rejects_known_bad_patterns(broad_entry: str) -> None:
    """``_is_broad_ignore`` must flag every bare-category form the policy bans.

    Pins the validator against the literal patterns the review highlights so
    future loosening of either the pyproject filters or the validator regex
    fails this test instead of silently re-opening the gate.
    """
    assert _is_broad_ignore(broad_entry), (
        f"validator missed broad ignore pattern: {broad_entry!r}. "
        f"The bare-category form is exactly what the zero-warning policy bans."
    )


@pytest.mark.parametrize(
    "narrow_entry",
    [
        "ignore:unclosed database in:ResourceWarning:sqlite3:",
        "ignore::pytest.PytestUnraisableExceptionWarning:_pytest.unraisableexception:",
        "ignore:.*deprecated.*:DeprecationWarning:third_party.legacy:",
    ],
)
def test_broad_ignore_validator_accepts_narrow_patterns(narrow_entry: str) -> None:
    """The validator must accept properly-narrow filters (message OR module)."""
    assert not _is_broad_ignore(narrow_entry), (
        f"validator falsely flagged a narrow filter as broad: {narrow_entry!r}"
    )


# ---- C. No enabled no-op project rules --------------------------------------


def _is_noop_rule_body(rule_cls: type) -> bool:
    """Heuristic: rule's ``check`` body returns ``[]`` unconditionally."""
    source_file = sys.modules[rule_cls.__module__].__file__
    if source_file is None:
        return False
    tree = ast.parse(Path(source_file).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != rule_cls.__name__:
            continue
        for item in node.body:
            if not isinstance(item, ast.FunctionDef) or item.name != "check":
                continue
            statements = [s for s in item.body if not isinstance(s, ast.Expr)]
            # Two flavours of no-op:
            #   1) `return []`
            #   2) Single short-circuit guard followed by `return []` with no
            #      issue-emitting logic in between (the STG008 placeholder).
            if len(statements) == 1 and isinstance(statements[0], ast.Return):
                value = statements[0].value
                if isinstance(value, ast.List) and not value.elts:
                    return True
            if len(statements) <= 3:
                returns = [s for s in statements if isinstance(s, ast.Return)]
                has_issue_construct = any(
                    isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name)
                    and n.func.id == "Issue"
                    for n in ast.walk(item)
                )
                if returns and not has_issue_construct:
                    return True
    return False


def test_test_quality_toml_has_no_enabled_noop_rules() -> None:
    data = tomllib.loads(TEST_QUALITY_TOML.read_text(encoding="utf-8"))
    enabled = {k for k, v in data.get("project_rules", {}).items() if v}
    offenders: list[str] = []
    for rule in ALL_RULES:
        if rule.id in enabled and _is_noop_rule_body(type(rule)):
            offenders.append(rule.id)
    assert not offenders, (
        f"Enabled project rules must have real detection logic. "
        f"No-op enabled rules: {offenders}. Either implement them or set "
        f"`<rule_id> = false` in backend/test-quality.toml with a TODO."
    )


# ---- D. Workflow has no continue-on-error on quality path -------------------


_CONTINUE_ON_ERROR = re.compile(r"^(?P<indent> *)continue-on-error:\s*true\s*$", re.MULTILINE)


def _find_continue_on_error_lines(workflow_path: Path) -> list[tuple[int, str]]:
    text = workflow_path.read_text(encoding="utf-8")
    hits: list[tuple[int, str]] = []
    for match in _CONTINUE_ON_ERROR.finditer(text):
        line_no = text[: match.start()].count("\n") + 1
        # Capture the preceding non-blank, non-comment line for context: it is
        # usually the step name. We allow steps that document an explicit
        # non-blocking carve-out (e.g. Bandit) — these include the substring
        # "non-blocking" in a leading comment.
        prior_lines = text[: match.start()].rsplit("\n", 6)[-6:]
        context_block = "\n".join(prior_lines)
        hits.append((line_no, context_block))
    return hits


def test_test_quality_workflow_has_no_undocumented_soft_fail() -> None:
    hits = _find_continue_on_error_lines(TEST_QUALITY_WORKFLOW)
    undocumented = [(line_no, ctx) for line_no, ctx in hits if "non-blocking" not in ctx.lower()]
    assert not undocumented, (
        "test-quality.yml has `continue-on-error: true` without a documented "
        "`non-blocking` rationale on the quality path. Per #262, soft-fails must "
        "either be removed or explicitly carved out as non-blocking. "
        f"Offending steps: {[line for line, _ in undocumented]}"
    )


def test_nightly_quality_workflow_has_no_undocumented_soft_fail() -> None:
    hits = _find_continue_on_error_lines(NIGHTLY_WORKFLOW)
    undocumented = [(line_no, ctx) for line_no, ctx in hits if "non-blocking" not in ctx.lower()]
    assert not undocumented, (
        "nightly-backend-quality.yml has `continue-on-error: true` without a "
        "documented `non-blocking` rationale. Per #262, nightly quality jobs "
        "must hard-fail. "
        f"Offending lines: {[line for line, _ in undocumented]}"
    )
