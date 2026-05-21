from __future__ import annotations

import argparse
import ast
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

TRACKED_FIXTURES = (
    "db_session",
    "app_client",
    "client",
    "session",
    "redis_client",
    "postgres_url",
)
DB_HEAVY_PATTERNS = (
    "create_all",
    "drop_all",
    "engine",
    "SessionLocal",
    "db_session.add",
    "db_session.commit",
    "db_session.flush",
    "metadata.create_all",
)
SCHEMA_PATTERNS = (
    "create_all",
    "drop_all",
    "metadata.create_all",
    "alembic",
)


def iter_test_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if path.name.startswith("test_") or path.name.endswith("_test.py")
    )


def _decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _decorator_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ""


def _is_fixture(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        _decorator_name(decorator).endswith("pytest.fixture") for decorator in node.decorator_list
    )


def _is_test(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return node.name.startswith("test_")


def _function_source(node: ast.FunctionDef | ast.AsyncFunctionDef, lines: list[str]) -> str:
    start = node.lineno - 1
    end = node.end_lineno or node.lineno
    return "\n".join(lines[start:end])


def audit_file(path: Path, root: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    lines = text.splitlines()

    tests = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_test(node)
    ]
    fixtures = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_fixture(node)
    ]

    fixture_usage: Counter[str] = Counter()
    db_heavy_tests: list[str] = []
    schema_tests: list[str] = []

    for test in tests:
        arg_names = {arg.arg for arg in test.args.args}
        for fixture_name in TRACKED_FIXTURES:
            if fixture_name in arg_names:
                fixture_usage[fixture_name] += 1

        source = _function_source(test, lines)
        if any(pattern in source for pattern in DB_HEAVY_PATTERNS):
            db_heavy_tests.append(test.name)
        if any(pattern in source for pattern in SCHEMA_PATTERNS):
            schema_tests.append(test.name)

    return {
        "path": str(path.relative_to(root)).replace("\\", "/"),
        "test_count": len(tests),
        "fixture_count": len(fixtures),
        "tracked_fixture_usage": dict(sorted(fixture_usage.items())),
        "db_heavy_tests": db_heavy_tests,
        "schema_tests": schema_tests,
    }


def build_report(root: Path) -> dict[str, Any]:
    files = [audit_file(path, root) for path in iter_test_files(root)]
    fixture_totals: Counter[str] = Counter()
    files_by_fixture: dict[str, list[str]] = defaultdict(list)

    for file_report in files:
        usage = file_report["tracked_fixture_usage"]
        for fixture_name, count in usage.items():
            fixture_totals[fixture_name] += int(count)
            files_by_fixture[fixture_name].append(str(file_report["path"]))

    return {
        "summary": {
            "files": len(files),
            "tests": sum(int(file_report["test_count"]) for file_report in files),
            "fixtures": sum(int(file_report["fixture_count"]) for file_report in files),
            "tracked_fixture_usage": dict(sorted(fixture_totals.items())),
            "db_heavy_tests": sum(len(file_report["db_heavy_tests"]) for file_report in files),
            "schema_tests": sum(len(file_report["schema_tests"]) for file_report in files),
        },
        "files_by_fixture": {key: sorted(value) for key, value in sorted(files_by_fixture.items())},
        "files": files,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit pytest fixture usage without importing the app."
    )
    parser.add_argument("--path", default="tests", help="Test root to audit")
    parser.add_argument("--output", required=True, help="Path to write fixture audit JSON")
    args = parser.parse_args(argv)

    root = Path(args.path)
    report = build_report(root)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
