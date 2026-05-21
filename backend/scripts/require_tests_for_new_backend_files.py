from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

EXCLUDED_NAME_SUFFIXES = (
    "__init__.py",
    "schemas.py",
)
EXCLUDED_PATH_PARTS = {
    "migrations",
    "contracts",
}
TEST_ROOT = Path("backend/tests")
APP_ROOT = Path("backend/app")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Require backend tests when new production Python files are added."
    )
    parser.add_argument("--base", default="origin/main", help="Base git ref for diff")
    args = parser.parse_args(argv)

    added_prod_files = _added_backend_app_files(args.base)
    if not added_prod_files:
        print("No new backend production files detected.")
        return 0

    changed_tests = _changed_test_files(args.base)
    if changed_tests:
        print("New backend production files detected and tests changed:")
        for path in added_prod_files:
            print(f"  production: {path}")
        for path in changed_tests:
            print(f"  test: {path}")
        return 0

    print("New backend production files require corresponding backend test changes:", file=sys.stderr)
    for path in added_prod_files:
        print(f"  - {path}", file=sys.stderr)
    print("Add or update backend/tests/**, or justify an explicit exemption in this script.", file=sys.stderr)
    return 1


def _added_backend_app_files(base: str) -> list[Path]:
    return [
        path
        for path in _git_changed_paths(base, diff_filter="A", pathspec="backend/app/**/*.py")
        if _is_required_production_file(path)
    ]


def _changed_test_files(base: str) -> list[Path]:
    return _git_changed_paths(base, diff_filter="ACMR", pathspec="backend/tests/**/*.py")


def _git_changed_paths(base: str, *, diff_filter: str, pathspec: str) -> list[Path]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"--diff-filter={diff_filter}", base, "--", pathspec],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git diff failed for base {base!r}")
    return [Path(line) for line in result.stdout.splitlines() if line.strip()]


def _is_required_production_file(path: Path) -> bool:
    return (
        _is_under(path, APP_ROOT)
        and not any(str(path).endswith(suffix) for suffix in EXCLUDED_NAME_SUFFIXES)
        and not any(part in EXCLUDED_PATH_PARTS for part in path.parts)
    )


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"require_tests_for_new_backend_files: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
