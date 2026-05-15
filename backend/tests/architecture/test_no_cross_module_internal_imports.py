from __future__ import annotations

import ast
from pathlib import Path


APP_ROOT = Path("app")
MODULES_ROOT = APP_ROOT / "modules"
PUBLIC_SUBMODULES = {
    "contracts",
    "context",
    "dependencies",
    "events",
    "interfaces",
    "jobs",
    "module",
    "router",
    "service",
}
SHARED_MODULES = {"contracts", "registry"}


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


def _feature_module_for(path: Path) -> str | None:
    parts = path.parts
    try:
        index = parts.index("modules")
    except ValueError:
        return None
    if len(parts) <= index + 1:
        return None
    module = parts[index + 1]
    if module in SHARED_MODULES or module == "__pycache__":
        return None
    return module


def _is_allowed_cross_module_import(imported: str, source_module: str) -> bool:
    prefix = "app.modules."
    if not imported.startswith(prefix):
        return True

    remainder = imported[len(prefix) :]
    imported_module = remainder.split(".", 1)[0]
    if imported_module in SHARED_MODULES or imported_module == source_module:
        return True

    if "." not in remainder:
        return True

    submodule = remainder.split(".", 2)[1]
    return submodule in PUBLIC_SUBMODULES


def test_feature_modules_do_not_import_other_module_internals() -> None:
    violations: list[str] = []
    for source in _python_files(MODULES_ROOT):
        source_module = _feature_module_for(source)
        if source_module is None:
            continue
        for imported in _imports(source):
            if _is_allowed_cross_module_import(imported, source_module):
                continue
            violations.append(
                "\n".join(
                    [
                        "Illegal cross-module internal import detected:",
                        f"Source: {_module_name(source)}",
                        f"Imported: {imported}",
                        "Allowed: app.modules.<module>, app.modules.<module>.contracts, "
                        "app.modules.<module>.interfaces, app.modules.<module>.service, "
                        "app.modules.<module>.jobs, app.modules.<module>.events",
                    ]
                )
            )

    assert violations == []


def test_module_packages_define_explicit_public_exports() -> None:
    missing_or_wildcard: list[str] = []
    for init_file in [MODULES_ROOT / "__init__.py", *MODULES_ROOT.glob("*/__init__.py")]:
        tree = ast.parse(init_file.read_text(encoding="utf-8"), filename=str(init_file))
        all_assignments = [
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
            )
        ]
        if not all_assignments:
            missing_or_wildcard.append(f"{init_file}: missing explicit __all__")
            continue
        value = all_assignments[-1].value
        if not isinstance(value, (ast.List, ast.Tuple)):
            missing_or_wildcard.append(f"{init_file}: __all__ must be a list/tuple literal")
            continue
        for item in value.elts:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                missing_or_wildcard.append(f"{init_file}: __all__ entries must be string literals")
            elif item.value == "*":
                missing_or_wildcard.append(f"{init_file}: wildcard public export is forbidden")

    assert missing_or_wildcard == []
