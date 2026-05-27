from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = BACKEND_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from legacy_wrapper_audit import WRAPPERS  # noqa: E402


MODULE_ROOTS = (
    Path("app/modules/account_safety"),
    Path("app/modules/account_editing"),
    Path("app/modules/account_profile_completeness"),
    Path("app/modules/account_lifecycle"),
    Path("app/modules/neuro_commenting"),
    Path("app/modules/warmup"),
)
LEGACY_IMPORTS = tuple(
    spec.legacy_path for spec in WRAPPERS if "backend/app/modules" in spec.forbidden_importers
)
WRAPPER_PATHS = tuple(Path(spec.file).relative_to("backend") for spec in WRAPPERS)


def _python_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def _module_name(path: Path) -> str:
    return ".".join(path.relative_to(BACKEND_ROOT).with_suffix("").parts)


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
    violations: list[str] = []
    for root in MODULE_ROOTS:
        for source in _python_files(BACKEND_ROOT / root):
            for imported in _imports(source):
                if any(_matches(imported, forbidden) for forbidden in LEGACY_IMPORTS):
                    violations.append(f"{_module_name(source)} imports {imported}")

    assert violations == []


def test_legacy_wrappers_have_compatibility_docstrings() -> None:
    violations = [
        str(path)
        for path in WRAPPER_PATHS
        if not _has_wrapper_docstring((BACKEND_ROOT / path).read_text(encoding="utf-8"))
    ]

    assert violations == []


def _has_wrapper_docstring(source: str) -> bool:
    return (
        "Compatibility wrapper." in source
        and "Canonical owner:" in source
        and "Do not add new behavior here." in source
    )
