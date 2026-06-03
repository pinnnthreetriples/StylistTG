"""Core types and helpers for the test quality analyzer."""

from __future__ import annotations

import ast
import hashlib
import re
import tomllib
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import TypeAlias


# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------


FunctionNode: TypeAlias = ast.FunctionDef | ast.AsyncFunctionDef


class Severity(IntEnum):
    INFO = 0
    WARNING = 1
    CRITICAL = 2

    @classmethod
    def from_str(cls, s: str) -> "Severity":
        return cls[s.upper()]


@dataclass
class Issue:
    rule_id: str
    rule_type: str
    severity: Severity
    file: str
    line: int
    message: str
    recommendation: str

    def fingerprint(self) -> str:
        """Line-shift-resilient fingerprint: rule + file + message (no line number)."""
        content = f"{self.rule_id}:{self.file}:{self.message}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class FileContext:
    path: Path
    relative_path: str
    source: str
    tree: ast.AST
    lines: list[str]
    suppressions: dict[str, set[str]]  # line_or_file -> set of rule_ids
    file_suppressions: set[str]
    suppression_warnings: list[Issue]


@dataclass
class AnalyzerConfig:
    tests_paths: list[str] = field(default_factory=lambda: ["tests"])
    source_paths: list[str] = field(default_factory=lambda: ["app"])
    external_markers: list[str] = field(
        default_factory=lambda: ["live", "integration", "redis", "postgres", "slow"]
    )
    max_assertions_per_test: int = 12
    duplicate_min_lines: int = 10
    duplicate_similarity: float = 0.90
    severity_overrides: dict[str, Severity] = field(default_factory=lambda: {})
    project_rules_enabled: dict[str, bool] = field(default_factory=lambda: {})

    @classmethod
    def from_toml(cls, path: Path) -> "AnalyzerConfig":
        with open(path, "rb") as f:
            data = tomllib.load(f)
        config = cls()
        if "paths" in data:
            config.tests_paths = data["paths"].get("tests", config.tests_paths)
            config.source_paths = data["paths"].get("source", config.source_paths)
        if "pytest" in data:
            config.external_markers = data["pytest"].get(
                "external_markers", config.external_markers
            )
        if "thresholds" in data:
            config.max_assertions_per_test = data["thresholds"].get(
                "max_assertions_per_test", config.max_assertions_per_test
            )
            config.duplicate_min_lines = data["thresholds"].get(
                "duplicate_min_lines", config.duplicate_min_lines
            )
            config.duplicate_similarity = data["thresholds"].get(
                "duplicate_similarity", config.duplicate_similarity
            )
        if "severity" in data:
            for key, val in data["severity"].items():
                config.severity_overrides[key] = Severity.from_str(val)
        if "project_rules" in data:
            config.project_rules_enabled = data["project_rules"]
        return config


# ---------------------------------------------------------------------------
# Rule base class
# ---------------------------------------------------------------------------


class Rule:
    id: str = ""
    type: str = ""
    default_severity: Severity = Severity.WARNING

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SUPPRESSION_RE = re.compile(r"#\s*test-analyzer:\s*disable=(\w+)\b(.*)$")
_FILE_SUPPRESSION_RE = re.compile(r"#\s*test-analyzer:\s*disable-file=(\w+)\b(.*)$")
_FIELD_REASON_RE = re.compile(r'reason="([^"]*)"')
# Permissive: capture any value so malformed `issue="abc"` still reaches the
# validator (which emits META002). A strict `#\d+` regex would silently
# drop typos — the same loophole the expiry field used to have.
_FIELD_ISSUE_RE_PERMISSIVE = re.compile(r'issue="([^"]*)"')
_ISSUE_VALID_RE = re.compile(r"^#\d+$")
# Permissive `expires="..."` regex: any quoted value is captured so a
# malformed date still reaches `_maybe_expiry_warning`, which then emits
# META003. A strict `\d{4}-\d{2}-\d{2}` regex would let bad values slip
# through silently — exactly the loophole the policy must close.
_FIELD_EXPIRES_RE = re.compile(r'expires="([^"]*)"')
# `permanent="true"` (or any non-empty value) opts the suppression out of
# the issue/expires requirement. Use sparingly for genuine analyzer false
# positives — `reason=` is still required, and reviewers see the field
# explicitly in the diff.
_FIELD_PERMANENT_RE = re.compile(r'permanent="([^"]*)"')


def _parse_suppression_fields(
    tail: str,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Return ``(reason, issue, expires, permanent)`` from the comment tail.

    Each element is the raw captured value if the field is present (possibly
    empty string for ``field=""``), or ``None`` if the field is absent.
    Distinguishing absent vs empty is required by the strict suppression
    policy: missing/empty/malformed values all fail the gate.
    """
    reason_match = _FIELD_REASON_RE.search(tail)
    issue_match = _FIELD_ISSUE_RE_PERMISSIVE.search(tail)
    expires_match = _FIELD_EXPIRES_RE.search(tail)
    permanent_match = _FIELD_PERMANENT_RE.search(tail)
    return (
        reason_match.group(1) if reason_match else None,
        issue_match.group(1) if issue_match else None,
        expires_match.group(1) if expires_match else None,
        permanent_match.group(1) if permanent_match else None,
    )


def _maybe_expiry_warning(
    rule_id: str, expires: str | None, *, relative_path: str, line: int
) -> Issue | None:
    """Return META003 unless ``expires`` is a valid future ISO date.

    Strict contract (suppressions must expire, not linger):

    - ``expires`` is ``None`` (field absent)        → META003 CRITICAL
    - ``expires`` is ``""`` (field present, empty)  → META003 CRITICAL
    - ``expires`` is not ISO YYYY-MM-DD             → META003 CRITICAL
    - ``expires`` is a past date                    → META003 CRITICAL
    - ``expires`` is today or any future date       → clean

    ``permanent="..."`` suppressions skip this check entirely by not
    invoking ``_maybe_expiry_warning`` at the caller level.
    """
    from datetime import date

    if expires is None:
        return Issue(
            rule_id="META003",
            rule_type="meta",
            severity=Severity.CRITICAL,
            file=relative_path,
            line=line,
            message=(
                f"Suppression for {rule_id} is missing required expires=. "
                f"Strict policy: every suppression must expire."
            ),
            recommendation=(
                'Add expires="YYYY-MM-DD" with a real future date, or '
                'mark the suppression as permanent="true" (for analyzer false '
                "positives only; see docs/quality/QUALITY_GATES.md)."
            ),
        )
    if not expires.strip():
        return Issue(
            rule_id="META003",
            rule_type="meta",
            severity=Severity.CRITICAL,
            file=relative_path,
            line=line,
            message=(
                f'Suppression for {rule_id} has empty expires=""; strict '
                f"policy forbids unbounded suppressions."
            ),
            recommendation=(
                'Replace expires="" with a real future ISO date, or use '
                'permanent="true" for documented false positives.'
            ),
        )
    try:
        expiry = date.fromisoformat(expires)
    except ValueError:
        return Issue(
            rule_id="META003",
            rule_type="meta",
            severity=Severity.CRITICAL,
            file=relative_path,
            line=line,
            message=(
                f"Suppression for {rule_id} has malformed expires={expires!r}; "
                f"must be ISO YYYY-MM-DD."
            ),
            recommendation='Use expires="YYYY-MM-DD" with a valid ISO date.',
        )
    if date.today() > expiry:
        return Issue(
            rule_id="META003",
            rule_type="meta",
            severity=Severity.CRITICAL,
            file=relative_path,
            line=line,
            message=(
                f"Suppression for {rule_id} expired on {expires}; remove the "
                f"suppression or renew the expiry after re-justifying."
            ),
            recommendation="Replace the suppressed code with a strict assertion.",
        )
    return None


def parse_suppressions(
    lines: list[str],
    relative_path: str,
) -> tuple[dict[str, set[str]], set[str], list[Issue]]:
    """Parse inline and file-level suppressions, return (line_supprs, file_supprs, warnings).

    Each suppression comment supports four fields:

    - ``reason="..."`` — required; missing → **META001** WARNING.
    - ``issue="#NNN"`` — required unless ``permanent="true"``; missing or
      malformed → **META002** CRITICAL.
    - ``expires="YYYY-MM-DD"`` — required unless ``permanent="true"``;
      missing, empty, malformed, or past expiry → **META003** CRITICAL.
    - ``permanent="..."`` — optional opt-out for *analyzer false positives*.
      When non-empty, ``issue=``/``expires=`` are no longer required, but
      ``reason=`` still is. Use sparingly; reviewers see the explicit field
      in the diff.

    The fields can appear in any order. Unrecognised fields are ignored.
    """
    line_suppressions: dict[str, set[str]] = {}
    file_suppressions: set[str] = set()
    warnings: list[Issue] = []

    def _emit_warnings(
        rule_id: str,
        reason: str | None,
        issue: str | None,
        expires: str | None,
        permanent: str | None,
        line_no: int,
    ) -> None:
        if not reason:
            warnings.append(
                Issue(
                    rule_id="META001",
                    rule_type="meta",
                    severity=Severity.WARNING,
                    file=relative_path,
                    line=line_no,
                    message=f"Suppression for {rule_id} without reason=",
                    recommendation='Add reason="..." to suppression comment',
                )
            )
        # `permanent="<non-empty>"` opts out of issue/expires requirements.
        if permanent and permanent.strip():
            return
        # Strict issue= check.
        if issue is None:
            warnings.append(
                Issue(
                    rule_id="META002",
                    rule_type="meta",
                    severity=Severity.CRITICAL,
                    file=relative_path,
                    line=line_no,
                    message=(
                        f"Suppression for {rule_id} is missing required issue=. "
                        f"Every deferred suppression must reference a tracking issue."
                    ),
                    recommendation=(
                        'Add issue="#NNN" pointing at the follow-up issue, or '
                        'mark as permanent="true" for analyzer false positives.'
                    ),
                )
            )
        elif not _ISSUE_VALID_RE.match(issue):
            warnings.append(
                Issue(
                    rule_id="META002",
                    rule_type="meta",
                    severity=Severity.CRITICAL,
                    file=relative_path,
                    line=line_no,
                    message=(
                        f"Suppression for {rule_id} has malformed issue={issue!r}; "
                        f"expected '#NNN' (e.g. '#263')."
                    ),
                    recommendation='Use issue="#NNN" referencing a real tracking issue.',
                )
            )
        expiry_issue = _maybe_expiry_warning(
            rule_id, expires, relative_path=relative_path, line=line_no
        )
        if expiry_issue is not None:
            warnings.append(expiry_issue)

    for i, line in enumerate(lines, 1):
        m = _FILE_SUPPRESSION_RE.search(line)
        if m:
            rule_id = m.group(1)
            reason, issue, expires, permanent = _parse_suppression_fields(m.group(2))
            file_suppressions.add(rule_id)
            _emit_warnings(rule_id, reason, issue, expires, permanent, i)
            continue
        m = _SUPPRESSION_RE.search(line)
        if m:
            rule_id = m.group(1)
            reason, issue, expires, permanent = _parse_suppression_fields(m.group(2))
            key = str(i + 1)  # suppression applies to next line
            line_suppressions.setdefault(key, set()).add(rule_id)
            _emit_warnings(rule_id, reason, issue, expires, permanent, i)
    return line_suppressions, file_suppressions, warnings


def _is_test_function(node: FunctionNode) -> bool:
    return node.name.startswith("test_")


def get_test_functions(tree: ast.AST) -> list[FunctionNode]:
    funcs: list[FunctionNode] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_test_function(node):
                funcs.append(node)
    return funcs


def count_asserts(node: ast.AST) -> int:
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            count += 1
        elif isinstance(child, ast.Call):
            func = child.func
            if (isinstance(func, ast.Attribute) and func.attr.startswith("assert")) or (
                isinstance(func, ast.Name) and func.id.startswith("assert")
            ):
                count += 1
    return count


def has_decorator(func: FunctionNode, name: str) -> bool:
    for dec in func.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == name:
            return True
        if isinstance(dec, ast.Attribute) and dec.attr == name:
            return True
        if isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Attribute) and dec.func.attr == name:
                return True
            if isinstance(dec.func, ast.Name) and dec.func.id == name:
                return True
    return False


def has_marker(func: FunctionNode, marker: str) -> bool:
    for dec in func.decorator_list:
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            if dec.func.attr == marker:
                return True
            if dec.func.attr == "mark":
                # @pytest.mark.live style
                pass
        if isinstance(dec, ast.Attribute):
            if dec.attr == marker:
                return True
    # Check pytest.mark.X pattern
    for dec in func.decorator_list:
        dec_src = ast.dump(dec)
        if f"attr='{marker}'" in dec_src:
            return True
    return False


def func_source(func: FunctionNode, lines: list[str]) -> str:
    start = func.lineno - 1
    if func.decorator_list:
        start = func.decorator_list[0].lineno - 1
    end = func.end_lineno or start + 1
    return "\n".join(lines[start:end])


def normalize_ast_block(source: str) -> str:
    """Normalize variable names and literals for duplicate detection."""
    normalized = re.sub(r'"[^"]*"', '"STR"', source)
    normalized = re.sub(r"'[^']*'", "'STR'", normalized)
    normalized = re.sub(r"\b\d+\b", "NUM", normalized)
    normalized = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "UUID",
        normalized,
    )
    return normalized
