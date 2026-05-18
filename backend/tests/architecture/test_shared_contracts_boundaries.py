from __future__ import annotations

import ast
from pathlib import Path


CONTRACTS_ROOT = Path("app/contracts")
MODULE_CONTRACTS_ROOT = Path("app/modules")
FORBIDDEN_SHARED_CONTRACT_IMPORTS = (
    "app.models",
    "app.modules",
    "app.services",
    "app.api",
    "app.db",
    "app.adapters",
    "app.job_queue",
    "app.workers",
    "app.runtime",
    "fastapi",
    "redis",
    "rq",
    "sqlalchemy",
)


def _python_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _matches(imported: str, forbidden: str) -> bool:
    return imported == forbidden or imported.startswith(f"{forbidden}.")


def test_shared_contracts_do_not_import_runtime_framework_or_persistence_layers() -> None:
    violations: list[str] = []
    for source in _python_files(CONTRACTS_ROOT):
        for imported in _imports(source):
            if any(
                _matches(imported, forbidden) for forbidden in FORBIDDEN_SHARED_CONTRACT_IMPORTS
            ):
                violations.append(f"{source} imports {imported}")

    assert violations == []


def test_account_editing_contracts_use_shared_contracts_instead_of_app_schemas() -> None:
    imports = _imports(MODULE_CONTRACTS_ROOT / "account_editing/contracts.py")

    assert "app.schemas" not in imports
    assert "app.contracts.accounts" in imports
    assert "app.contracts.jobs" in imports
    assert "app.contracts.safety" in imports


def test_warmup_contracts_do_not_depend_on_app_schemas() -> None:
    imports = _imports(MODULE_CONTRACTS_ROOT / "warmup/contracts.py")

    assert "app.schemas" not in imports
