from __future__ import annotations

import ast
from pathlib import Path


MODULE_ROOTS = (Path("app/modules/account_editing"), Path("app/modules/warmup"))
ACCOUNT_EDITING_LEGACY_IMPORTS = (
    "app.services.account_update_jobs",
    "app.services.account_update_plan",
    "app.workers.account_update_jobs",
)
WARMUP_LEGACY_IMPORTS = (
    "app.services.warmup",
    "app.services.warmup_worker",
    "app.services.warmup_dispatch",
    "app.services.warmup_isolation",
    "app.services.warmup_readiness",
    "app.services.warmup_p2p",
    "app.workers.warmup_jobs",
    "app.workers.warmup_dispatch_jobs",
)
WRAPPER_PATHS = (
    Path("app/api/account_update.py"),
    Path("app/api/warmup.py"),
    Path("app/services/account_update_jobs.py"),
    Path("app/services/account_update_plan.py"),
    Path("app/services/auth_context.py"),
    Path("app/workers/account_update_jobs.py"),
    Path("app/services/warmup.py"),
    Path("app/services/warmup_worker.py"),
    Path("app/services/warmup_dispatch.py"),
    Path("app/services/warmup_isolation.py"),
    Path("app/services/warmup_readiness.py"),
    Path("app/services/warmup_p2p.py"),
    Path("app/workers/warmup_jobs.py"),
    Path("app/workers/warmup_dispatch_jobs.py"),
)


def _python_files(root: Path) -> list[Path]:
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


def _matches(imported: str, forbidden: str) -> bool:
    return imported == forbidden or imported.startswith(f"{forbidden}.")


def test_modules_do_not_import_legacy_wrappers() -> None:
    forbidden_by_root = {
        Path("app/modules/account_editing"): ACCOUNT_EDITING_LEGACY_IMPORTS,
        Path("app/modules/warmup"): WARMUP_LEGACY_IMPORTS,
    }
    violations: list[str] = []
    for root in MODULE_ROOTS:
        for source in _python_files(root):
            for imported in _imports(source):
                if any(_matches(imported, forbidden) for forbidden in forbidden_by_root[root]):
                    violations.append(f"{_module_name(source)} imports {imported}")

    assert violations == []


def test_legacy_wrappers_have_compatibility_docstrings() -> None:
    violations = [
        str(path)
        for path in WRAPPER_PATHS
        if not _has_wrapper_docstring(path.read_text(encoding="utf-8"))
    ]

    assert violations == []


def _has_wrapper_docstring(source: str) -> bool:
    return (
        "Compatibility wrapper." in source
        and "Canonical owner:" in source
        and "Do not add new behavior here." in source
    )
