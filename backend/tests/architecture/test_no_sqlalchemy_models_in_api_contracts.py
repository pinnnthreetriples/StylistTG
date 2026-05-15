from __future__ import annotations

import ast
from pathlib import Path


APP_ROOT = Path("app")
CONTRACT_NAME_MARKERS = ("schema", "schemas", "contract", "contracts", "dto", "dtos")
FORBIDDEN_CONTRACT_IMPORTS = (
    "app.models",
    "fastapi",
    "redis",
    "rq",
    "sqlalchemy",
    "app.adapters.tdlib",
    "app.adapters.warmup_tdlib",
)


def _contract_files() -> list[Path]:
    candidates: list[Path] = []
    for path in APP_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        stem = path.stem.lower()
        if any(marker in stem for marker in CONTRACT_NAME_MARKERS):
            candidates.append(path)
    return candidates


def _module_name(path: Path) -> str:
    return ".".join(path.with_suffix("").parts)


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def test_api_contract_modules_do_not_import_runtime_or_persistence_layers() -> None:
    violations: list[str] = []
    for source in _contract_files():
        for imported in _imports(source):
            if any(
                imported == forbidden or imported.startswith(f"{forbidden}.")
                for forbidden in FORBIDDEN_CONTRACT_IMPORTS
            ):
                violations.append(
                    "\n".join(
                        [
                            "API/schema contract imports a forbidden runtime or persistence layer:",
                            f"Source: {_module_name(source)}",
                            f"Imported: {imported}",
                            "Expected: contracts use Pydantic/typed DTOs and primitive IDs only.",
                        ]
                    )
                )

    assert violations == []


def test_contract_scan_covers_known_schema_files() -> None:
    scanned = {str(path).replace("\\", "/") for path in _contract_files()}

    assert "app/schemas.py" in scanned
    assert "app/modules/account_editing/contracts.py" in scanned
    assert "app/modules/warmup/contracts.py" in scanned
