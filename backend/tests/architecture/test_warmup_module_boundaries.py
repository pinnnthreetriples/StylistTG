from __future__ import annotations

import ast
from pathlib import Path


WARMUP_ROOT = Path("app/modules/warmup")
WARMUP_INIT = WARMUP_ROOT / "__init__.py"
WARMUP_CONTRACTS = WARMUP_ROOT / "contracts.py"
WARMUP_REPOSITORY = WARMUP_ROOT / "repository.py"
WARMUP_POLICIES = WARMUP_ROOT / "policies.py"
WARMUP_ROUTER = WARMUP_ROOT / "router.py"
WARMUP_SERVICE = WARMUP_ROOT / "service.py"
WARMUP_LAYER_MODULES = {"read_models", "queries", "commands"}
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
CONTRACT_FORBIDDEN_IMPORTS = (
    "app.models",
    "sqlalchemy",
    "fastapi",
    "redis",
    "rq",
    "app.adapters.tdlib",
    "app.adapters.warmup_tdlib",
)
REPOSITORY_FORBIDDEN_IMPORTS = ("fastapi", "app.api")
POLICY_FORBIDDEN_IMPORTS = (
    "app.api",
    "app.db",
    "app.job_queue",
    "app.modules.warmup.router",
    "fastapi",
    "redis",
    "rq",
    "sqlalchemy",
)
SERVICE_FACADE_FORBIDDEN_IMPORTS = (
    "app.job_queue",
    "app.models",
    "app.modules.warmup.isolation",
    "app.modules.warmup.readiness",
    "redis",
)


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


def _has_import(imported: str, forbidden: str) -> bool:
    return imported == forbidden or imported.startswith(f"{forbidden}.")


def test_warmup_router_does_not_import_orm_or_sqlalchemy_queries() -> None:
    violations: list[str] = []
    for imported, names in _imports(WARMUP_ROUTER):
        if imported == "app.models" or imported.startswith("app.models."):
            violations.append(f"{_module_name(WARMUP_ROUTER)} imports {imported}")
        if imported == "sqlalchemy" and {"select", "func"} & set(names):
            violations.append(f"{_module_name(WARMUP_ROUTER)} imports sqlalchemy {names}")

    assert violations == []


def test_warmup_layer_modules_exist_and_are_public() -> None:
    missing = sorted(
        module for module in WARMUP_LAYER_MODULES if not (WARMUP_ROOT / f"{module}.py").exists()
    )
    init_source = WARMUP_INIT.read_text(encoding="utf-8")

    assert missing == []
    for module in WARMUP_LAYER_MODULES:
        assert f'"{module}"' in init_source


def test_warmup_module_does_not_import_legacy_warmup_paths() -> None:
    violations: list[str] = []
    for source in _python_files(WARMUP_ROOT):
        for imported, _names in _imports(source):
            if imported in LEGACY_WARMUP_IMPORTS:
                violations.append(f"{_module_name(source)} imports {imported}")

    assert violations == []


def test_warmup_contracts_do_not_import_runtime_or_persistence() -> None:
    violations = [
        f"{_module_name(WARMUP_CONTRACTS)} imports {imported}"
        for imported, _names in _imports(WARMUP_CONTRACTS)
        if any(_has_import(imported, forbidden) for forbidden in CONTRACT_FORBIDDEN_IMPORTS)
    ]

    assert violations == []


def test_warmup_repository_does_not_import_api_helpers() -> None:
    violations = [
        f"{_module_name(WARMUP_REPOSITORY)} imports {imported}"
        for imported, _names in _imports(WARMUP_REPOSITORY)
        if any(_has_import(imported, forbidden) for forbidden in REPOSITORY_FORBIDDEN_IMPORTS)
    ]

    assert violations == []


def test_warmup_policies_stay_pure_domain_rules() -> None:
    violations: list[str] = []
    for imported, names in _imports(WARMUP_POLICIES):
        if any(_has_import(imported, forbidden) for forbidden in POLICY_FORBIDDEN_IMPORTS):
            violations.append(f"{_module_name(WARMUP_POLICIES)} imports {imported}")
        if imported == "sqlalchemy.orm" and "Session" in names:
            violations.append(f"{_module_name(WARMUP_POLICIES)} imports sqlalchemy.orm.Session")

    assert violations == []


def test_only_warmup_router_imports_fastapi() -> None:
    violations = [
        f"{_module_name(source)} imports {imported}"
        for source in _python_files(WARMUP_ROOT)
        if source != WARMUP_ROUTER
        for imported, _names in _imports(source)
        if _has_import(imported, "fastapi")
    ]

    assert violations == []


def test_warmup_service_is_facade_not_runtime_owner() -> None:
    violations = [
        f"{_module_name(WARMUP_SERVICE)} imports {imported}"
        for imported, _names in _imports(WARMUP_SERVICE)
        if any(_has_import(imported, forbidden) for forbidden in SERVICE_FACADE_FORBIDDEN_IMPORTS)
    ]

    assert violations == []


def test_warmup_package_does_not_eager_import_feature_module_metadata() -> None:
    imports = _imports(WARMUP_INIT)

    assert ("app.modules.warmup.module", ("module",)) not in imports
