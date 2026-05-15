from __future__ import annotations

import ast
from pathlib import Path

from app.modules.auth import context, dependencies
from app.services import auth_context


AUTH_ROOT = Path("app/modules/auth")
PURE_AUTH_FILES = [
    AUTH_ROOT / "context.py",
    AUTH_ROOT / "contracts.py",
    AUTH_ROOT / "policies.py",
]
FORBIDDEN_PURE_IMPORTS = (
    "app.db",
    "app.models",
    "fastapi",
    "sqlalchemy",
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


def _matches(imported: str, forbidden: str) -> bool:
    return imported == forbidden or imported.startswith(f"{forbidden}.")


def test_auth_pure_modules_do_not_import_fastapi_sqlalchemy_or_models() -> None:
    violations: list[str] = []
    for source in PURE_AUTH_FILES:
        for imported in _imports(source):
            if any(_matches(imported, forbidden) for forbidden in FORBIDDEN_PURE_IMPORTS):
                violations.append(f"{source}: {imported}")

    assert violations == []


def test_auth_dependencies_is_only_auth_fastapi_import() -> None:
    violations: list[str] = []
    for source in AUTH_ROOT.glob("*.py"):
        if source.name == "dependencies.py":
            continue
        for imported in _imports(source):
            if _matches(imported, "fastapi"):
                violations.append(f"{source}: {imported}")

    assert violations == []
    assert any(
        _matches(imported, "fastapi") for imported in _imports(AUTH_ROOT / "dependencies.py")
    )


def test_auth_repository_has_no_presentation_imports() -> None:
    forbidden = ("app.api", "app.main", "fastapi")
    violations = [
        imported
        for imported in _imports(AUTH_ROOT / "repository.py")
        if any(_matches(imported, item) for item in forbidden)
    ]

    assert violations == []


def test_legacy_auth_context_is_compatibility_wrapper() -> None:
    source = Path("app/services/auth_context.py").read_text(encoding="utf-8")

    assert "Compatibility wrapper." in source
    assert "Canonical owner:" in source
    assert "Do not add new behavior here." in source
    assert auth_context.AuthContext is context.AuthContext
    assert auth_context.get_current_auth_context is dependencies.get_current_auth_context
    assert auth_context.require_authenticated is dependencies.require_authenticated
    assert auth_context.require_role is dependencies.require_role
    assert auth_context.require_mutation_permission is dependencies.require_mutation_permission


def test_module_routers_do_not_import_legacy_auth_context() -> None:
    module_routers = [
        Path("app/modules/account_editing/router.py"),
        Path("app/modules/warmup/router.py"),
    ]
    violations = [
        str(path)
        for path in module_routers
        if "app.services.auth_context" in path.read_text(encoding="utf-8")
    ]

    assert violations == []
