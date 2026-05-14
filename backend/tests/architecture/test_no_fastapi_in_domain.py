from __future__ import annotations

import ast
from pathlib import Path


APP_ROOT = Path("app")
DOMAIN_ROOTS = [
    APP_ROOT / "modules",
    APP_ROOT / "services",
    APP_ROOT / "workers",
    APP_ROOT / "job_queue",
    APP_ROOT / "storage",
    APP_ROOT / "adapters",
]

# Existing compatibility dependency provider. This file intentionally bridges
# FastAPI dependency injection and service-level auth context helpers.
FASTAPI_IMPORT_ALLOWLIST = {
    APP_ROOT / "services" / "auth_context.py",
}


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


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


def test_fastapi_imports_stay_out_of_domain_logic() -> None:
    violations: list[str] = []
    for root in DOMAIN_ROOTS:
        for source in _python_files(root):
            if source in FASTAPI_IMPORT_ALLOWLIST:
                continue
            if "modules" in source.parts and source.name == "router.py":
                continue
            for imported in _imports(source):
                if imported == "fastapi" or imported.startswith("fastapi."):
                    violations.append(
                        "\n".join(
                            [
                                "Illegal FastAPI import in domain/service layer:",
                                f"Source: {_module_name(source)}",
                                f"Imported: {imported}",
                                "Allowed: FastAPI imports belong in app.api, app.main, app.errors, "
                                "or an explicit architecture-test allowlist.",
                            ]
                        )
                    )

    assert violations == []


def test_fastapi_allowlist_is_explicit_and_existing() -> None:
    missing = [str(path) for path in FASTAPI_IMPORT_ALLOWLIST if not path.exists()]

    assert missing == []
