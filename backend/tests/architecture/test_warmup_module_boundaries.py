from __future__ import annotations

import ast
from pathlib import Path


WARMUP_ROOT = Path("app/modules/warmup")
WARMUP_INIT = WARMUP_ROOT / "__init__.py"
WARMUP_ROUTER = WARMUP_ROOT / "router.py"
LEGACY_WARMUP_IMPORTS = {
    "app.services.warmup",
    "app.services.warmup_worker",
    "app.services.warmup_dispatch",
    "app.services.warmup_isolation",
    "app.services.warmup_readiness",
    "app.services.warmup_p2p",
    "app.workers.warmup_jobs",
    "app.workers.warmup_dispatch_jobs",
}


def _python_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def _module_name(path: Path) -> str:
    return ".".join(path.with_suffix("").parts)


def _imports(path: Path) -> list[tuple[str, tuple[str, ...]]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[str, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, ()) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.module, tuple(alias.name for alias in node.names)))
    return imports


def test_warmup_router_does_not_import_orm_or_sqlalchemy_queries() -> None:
    violations: list[str] = []
    for imported, names in _imports(WARMUP_ROUTER):
        if imported == "app.models" or imported.startswith("app.models."):
            violations.append(f"{_module_name(WARMUP_ROUTER)} imports {imported}")
        if imported == "sqlalchemy" and {"select", "func"} & set(names):
            violations.append(f"{_module_name(WARMUP_ROUTER)} imports sqlalchemy {names}")

    assert violations == []


def test_warmup_module_does_not_import_legacy_warmup_paths() -> None:
    violations: list[str] = []
    for source in _python_files(WARMUP_ROOT):
        for imported, _names in _imports(source):
            if imported in LEGACY_WARMUP_IMPORTS:
                violations.append(f"{_module_name(source)} imports {imported}")

    assert violations == []


def test_warmup_package_does_not_eager_import_feature_module_metadata() -> None:
    imports = _imports(WARMUP_INIT)

    assert ("app.modules.warmup.module", ("module",)) not in imports
