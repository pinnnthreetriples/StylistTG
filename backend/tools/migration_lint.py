from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DROP_COLUMN_SAFE_COMMENT = "# safe: column unused in code since release"
ONLINE_SCHEMA_COMMENT = "# expected: requires online schema change"
EMPTY_TABLE_WHITELIST: frozenset[str] = frozenset()
LARGE_TABLES = {
    "account",
    "accounts",
    "account_quarantines",
    "account_status_observations",
    "cross_module_load_buckets",
    "neuro_comment_events",
}


@dataclass(frozen=True)
class MigrationIssue:
    path: Path
    line: int
    severity: str
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.severity}: {self.message}"


@dataclass
class MigrationReport:
    issues: list[MigrationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(issue.severity == "warning" for issue in self.issues)

    def extend(self, issues: list[MigrationIssue]) -> None:
        self.issues.extend(issues)


@dataclass(frozen=True)
class _OperationCall:
    node: ast.Call
    name: str
    table: str | None = None


def lint_paths(paths: list[Path]) -> MigrationReport:
    report = MigrationReport()
    for path in paths:
        if path.exists():
            report.extend(lint_migration(path, path.read_text(encoding="utf-8")))
    return report


def lint_migration(path: Path, source: str) -> list[MigrationIssue]:
    tree = ast.parse(source, filename=str(path))
    lines = source.splitlines()
    issues: list[MigrationIssue] = []
    for operation in _upgrade_operations(tree):
        node = operation.node
        call_name = operation.name
        if call_name == "op.add_column":
            issues.extend(_lint_add_column(path, node, table=operation.table))
        elif call_name == "op.alter_column":
            issues.extend(_lint_alter_column(path, node, table=operation.table))
        elif call_name == "op.drop_column":
            issues.extend(_lint_drop_column(path, lines, node))
        issues.extend(
            _lint_large_table_operation(path, lines, node, call_name, table=operation.table)
        )
    return issues


def _lint_add_column(path: Path, node: ast.Call, *, table: str | None) -> list[MigrationIssue]:
    batch_table = table
    table = batch_table or _literal_arg(node, 0)
    column_index = 0 if batch_table is not None else 1
    column = node.args[column_index] if len(node.args) > column_index else None
    if table in EMPTY_TABLE_WHITELIST or not isinstance(column, ast.Call):
        return []
    if _call_basename(column) != "Column":
        return []
    if _keyword_is_false(column, "nullable") and not _has_non_none_keyword(
        column, "server_default"
    ):
        return [
            _issue(
                path,
                node,
                "error",
                "op.add_column(nullable=False) requires server_default for existing rows",
            )
        ]
    return []


def _lint_alter_column(path: Path, node: ast.Call, *, table: str | None) -> list[MigrationIssue]:
    table = table or _literal_arg(node, 0)
    if table in EMPTY_TABLE_WHITELIST:
        return []
    if _keyword_is_false(node, "nullable") and not _has_non_none_keyword(node, "server_default"):
        return [
            _issue(
                path,
                node,
                "error",
                "op.alter_column(nullable=False) requires server_default "
                "or an empty-table whitelist",
            )
        ]
    return []


def _lint_drop_column(path: Path, lines: list[str], node: ast.Call) -> list[MigrationIssue]:
    if _has_nearby_comment(lines, node.lineno, DROP_COLUMN_SAFE_COMMENT):
        return []
    return [
        _issue(
            path,
            node,
            "error",
            f"op.drop_column requires two-deploy safety comment: {DROP_COLUMN_SAFE_COMMENT} X.Y",
        )
    ]


def _lint_large_table_operation(
    path: Path,
    lines: list[str],
    node: ast.Call,
    call_name: str,
    *,
    table: str | None,
) -> list[MigrationIssue]:
    if call_name not in {
        "op.add_column",
        "op.alter_column",
        "op.create_check_constraint",
        "op.create_index",
        "op.create_unique_constraint",
        "op.execute",
    }:
        return []
    table = table or _table_for_operation(node, call_name)
    if table not in LARGE_TABLES or _has_nearby_comment(lines, node.lineno, ONLINE_SCHEMA_COMMENT):
        return []
    return [
        _issue(
            path,
            node,
            "warning",
            f"{call_name} on large table {table!r} should document online schema "
            "change expectations",
        )
    ]


def changed_migration_paths(base: str) -> list[Path]:
    repo_root = _git_repo_root()
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
            base,
            "--",
            "backend/migrations/versions/*.py",
        ],
        cwd=repo_root,
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git diff failed for base {base!r}")
    return [repo_root / line for line in result.stdout.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint Alembic migrations for production safety.")
    parser.add_argument("--base", default="origin/main", help="Git ref used to find new migrations")
    parser.add_argument(
        "--paths",
        nargs="*",
        type=Path,
        help="Explicit migration paths for tests/local use",
    )
    args = parser.parse_args(argv)

    try:
        paths = args.paths if args.paths is not None else changed_migration_paths(args.base)
    except RuntimeError as exc:
        print(f"migration_lint: {exc}", file=sys.stderr)
        return 2
    report = lint_paths(paths)
    for issue in report.issues:
        stream = sys.stderr if issue.severity == "error" else sys.stdout
        print(issue.format(), file=stream)
    return 1 if report.has_errors else 0


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
        return f"{node.func.value.id}.{node.func.attr}"
    return ""


def _git_repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git rev-parse failed")
    return Path(result.stdout.strip())


def _upgrade_operations(tree: ast.AST) -> list[_OperationCall]:
    visitor = _UpgradeOperationVisitor()
    visitor.visit(tree)
    return visitor.operations


class _UpgradeOperationVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.operations: list[_OperationCall] = []
        self._batch_tables: dict[str, str] = {}
        self._functions: dict[str, ast.FunctionDef] = {}
        self._active_helpers: set[str] = set()

    def visit_Module(self, node: ast.Module) -> None:
        self._functions = {
            statement.name: statement
            for statement in node.body
            if isinstance(statement, ast.FunctionDef)
        }
        for statement in node.body:
            if isinstance(statement, ast.FunctionDef) and statement.name == "upgrade":
                for child in statement.body:
                    self.visit(child)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return None

    def visit_With(self, node: ast.With) -> None:
        added_aliases: list[str] = []
        for item in node.items:
            table = _batch_table(item.context_expr)
            if table is None or not isinstance(item.optional_vars, ast.Name):
                continue
            alias = item.optional_vars.id
            self._batch_tables[alias] = table
            added_aliases.append(alias)
        for statement in node.body:
            self.visit(statement)
        for alias in added_aliases:
            self._batch_tables.pop(alias, None)

    def visit_Call(self, node: ast.Call) -> None:
        operation = self._operation(node)
        if operation is not None:
            self.operations.append(operation)
        self._visit_helper_call(node)
        self.generic_visit(node)

    def _visit_helper_call(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Name):
            return
        helper_name = node.func.id
        helper = self._functions.get(helper_name)
        if (
            helper is None
            or helper_name in {"upgrade", "downgrade"}
            or helper_name in self._active_helpers
        ):
            return
        self._active_helpers.add(helper_name)
        try:
            for statement in helper.body:
                self.visit(statement)
        finally:
            self._active_helpers.remove(helper_name)

    def _operation(self, node: ast.Call) -> _OperationCall | None:
        call_name = _call_name(node)
        if call_name.startswith("op."):
            return _OperationCall(node=node, name=call_name)
        if not isinstance(node.func, ast.Attribute) or not isinstance(node.func.value, ast.Name):
            return None
        table = self._batch_tables.get(node.func.value.id)
        if table is None:
            return None
        return _OperationCall(node=node, name=f"op.{node.func.attr}", table=table)


def _batch_table(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call) or _call_name(node) != "op.batch_alter_table":
        return None
    return _literal_arg(node, 0)


def _call_basename(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _literal_arg(node: ast.Call, index: int) -> str | None:
    if len(node.args) <= index:
        return None
    value = node.args[index]
    return value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else None


def _has_non_none_keyword(node: ast.Call, name: str) -> bool:
    for keyword in node.keywords:
        if keyword.arg == name:
            return not (isinstance(keyword.value, ast.Constant) and keyword.value.value is None)
    return False


def _keyword_is_false(node: ast.Call, name: str) -> bool:
    for keyword in node.keywords:
        if keyword.arg == name:
            return isinstance(keyword.value, ast.Constant) and keyword.value.value is False
    return False


def _table_for_operation(node: ast.Call, call_name: str) -> str | None:
    if call_name in {
        "op.create_index",
        "op.create_unique_constraint",
        "op.create_check_constraint",
    }:
        return _literal_arg(node, 1)
    if call_name == "op.execute":
        return _table_from_execute(node)
    return _literal_arg(node, 0)


def _table_from_execute(node: ast.Call) -> str | None:
    sql = _literal_arg(node, 0)
    if sql is None:
        return None
    lowered = " ".join(sql.lower().split())
    for table in LARGE_TABLES:
        if f" {table} " in f" {lowered} ":
            return table
    return None


def _has_nearby_comment(lines: list[str], lineno: int, marker: str) -> bool:
    start = max(0, lineno - 3)
    end = min(len(lines), lineno + 1)
    return any(marker in line for line in lines[start:end])


def _issue(path: Path, node: ast.AST, severity: str, message: str) -> MigrationIssue:
    return MigrationIssue(
        path=path,
        line=getattr(node, "lineno", 1),
        severity=severity,
        message=message,
    )


if __name__ == "__main__":
    raise SystemExit(main())
