from __future__ import annotations

import ast
from pathlib import Path


APP_ROOT = Path("app")
CONTRACT_ROOTS = [APP_ROOT / "schemas.py", APP_ROOT / "modules"]
POLICY_MODULES = [
    APP_ROOT / "modules" / "account_editing" / "policies.py",
    APP_ROOT / "modules" / "warmup" / "policies.py",
]
REPOSITORY_MODULES = [
    APP_ROOT / "modules" / "account_editing" / "repository.py",
    APP_ROOT / "modules" / "warmup" / "repository.py",
]
ROUTER_MODULES = [
    APP_ROOT / "modules" / "account_editing" / "router.py",
    APP_ROOT / "modules" / "warmup" / "router.py",
]

FORBIDDEN_CONTRACT_IMPORTS = (
    "app.models",
    "fastapi",
    "redis",
    "rq",
    "sqlalchemy",
    "app.adapters.tdlib",
    "app.adapters.warmup_tdlib",
)
FORBIDDEN_POLICY_IMPORTS = (
    "app.api",
    "app.db",
    "fastapi",
    "redis",
    "rq",
    "sqlalchemy",
)
FORBIDDEN_REPOSITORY_IMPORTS = (
    "app.api",
    "app.main",
    "fastapi",
)


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _module_name(path: Path) -> str:
    return ".".join(path.with_suffix("").parts)


def _matches(imported: str, forbidden: str) -> bool:
    return imported == forbidden or imported.startswith(f"{forbidden}.")


def _contract_files() -> list[Path]:
    files = [APP_ROOT / "schemas.py"]
    files.extend(
        path
        for path in (APP_ROOT / "modules").glob("*/contracts.py")
        if "__pycache__" not in path.parts
    )
    contracts_root = APP_ROOT / "contracts"
    if contracts_root.exists():
        files.extend(
            path for path in contracts_root.rglob("*.py") if "__pycache__" not in path.parts
        )
    return files


def _violations(paths: list[Path], forbidden_imports: tuple[str, ...]) -> list[str]:
    violations: list[str] = []
    for source in paths:
        if not source.exists():
            violations.append(f"{source}: missing expected boundary file")
            continue
        for imported in _imports(source):
            if any(_matches(imported, forbidden) for forbidden in forbidden_imports):
                violations.append(f"{_module_name(source)} imports {imported}")
    return violations


def test_contracts_do_not_import_orm_or_runtime_layers() -> None:
    assert _violations(_contract_files(), FORBIDDEN_CONTRACT_IMPORTS) == []


def test_policies_do_not_import_db_session_query_or_api_layers() -> None:
    assert _violations(POLICY_MODULES, FORBIDDEN_POLICY_IMPORTS) == []


def test_repositories_do_not_import_fastapi_or_api_layers() -> None:
    assert _violations(REPOSITORY_MODULES, FORBIDDEN_REPOSITORY_IMPORTS) == []


def test_module_routers_do_not_import_orm_models() -> None:
    assert _violations(ROUTER_MODULES, ("app.models",)) == []
