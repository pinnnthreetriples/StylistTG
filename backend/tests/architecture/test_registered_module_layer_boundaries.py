from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from app.modules.registry import iter_modules, iter_workflows


APP_ROOT = Path("app")
MODULES_ROOT = APP_ROOT / "modules"
FORBIDDEN_CONTRACT_IMPORTS = (
    "app.models",
    "app.adapters",
    "app.job_queue",
    "app.runtime",
    "app.services",
    "app.workers",
    "fastapi",
    "redis",
    "rq",
    "sqlalchemy",
)
FORBIDDEN_POLICY_IMPORTS = (
    "app.db",
    "app.job_queue",
    "app.models",
    "app.runtime",
    "app.workers",
    "fastapi",
    "redis",
    "rq",
    "sqlalchemy",
)
FORBIDDEN_ROUTER_IMPORTS = ("app.models",)
FORBIDDEN_REPOSITORY_IMPORTS = ("app.api", "app.main", "fastapi")
FORBIDDEN_JOB_IMPORTS = (
    "app.api",
    "app.main",
    "app.models",
    "fastapi",
    "redis",
    "rq",
    "sqlalchemy",
)
FORBIDDEN_METADATA_IMPORTS = (
    "app.api",
    "app.main",
    "app.models",
    "app.services",
    "fastapi",
    "redis",
    "rq",
    "sqlalchemy",
)


@dataclass(frozen=True, slots=True)
class LayerDebtException:
    source: Path
    imported: str
    rationale: str


POLICY_LAYER_DEBT_EXCEPTIONS = {
    LayerDebtException(
        source=MODULES_ROOT / "account_editing" / "policies.py",
        imported="app.models",
        rationale="Existing account-editing policy reads model state until a pure policy DTO boundary exists.",
    ),
    LayerDebtException(
        source=MODULES_ROOT / "warmup" / "policies.py",
        imported="app.models",
        rationale="Existing warmup policy uses model enums until module contracts own pure status DTOs.",
    ),
}


def _registered_module_roots() -> list[Path]:
    return [MODULES_ROOT / module.name for module in iter_modules()]


def _import_from_base(path: Path, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    module_parts = list(path.with_suffix("").parts)
    if path.name == "__init__.py":
        module_parts.pop()
    else:
        module_parts.pop()
    if node.level > len(module_parts):
        return node.module or ""
    base_parts = module_parts[: len(module_parts) - node.level + 1]
    if node.module:
        base_parts.extend(node.module.split("."))
    return ".".join(base_parts)


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _import_from_base(path, node)
            imports.extend(f"{base}.{alias.name}" for alias in node.names if base)
    return imports


def _matches(imported: str, forbidden: str) -> bool:
    return imported == forbidden or imported.startswith(f"{forbidden}.")


def _violations_for(
    *, layer_filename: str, forbidden_imports: tuple[str, ...]
) -> list[tuple[Path, str]]:
    violations: list[tuple[Path, str]] = []
    for module_root in _registered_module_roots():
        source = module_root / layer_filename
        if not source.exists():
            continue
        for imported in _imports(source):
            if any(_matches(imported, forbidden) for forbidden in forbidden_imports):
                violations.append((source, imported))
    return violations


def _existing_layer_files(layer_filename: str) -> list[Path]:
    return [
        module_root / layer_filename
        for module_root in _registered_module_roots()
        if (module_root / layer_filename).exists()
    ]


def _is_allowed_policy_debt(source: Path, imported: str) -> bool:
    return any(
        exception.source == source
        and _matches(imported, exception.imported)
        and len(exception.rationale) >= 20
        for exception in POLICY_LAYER_DEBT_EXCEPTIONS
    )


def test_registered_modules_have_existing_roots() -> None:
    missing = [
        module_root for module_root in _registered_module_roots() if not module_root.exists()
    ]

    assert missing == []


def test_registered_module_contracts_stay_runtime_and_persistence_free() -> None:
    violations = _violations_for(
        layer_filename="contracts.py", forbidden_imports=FORBIDDEN_CONTRACT_IMPORTS
    )

    assert violations == []


def test_registered_module_policies_do_not_add_transport_runtime_or_persistence_imports() -> None:
    violations = [
        (source, imported)
        for source, imported in _violations_for(
            layer_filename="policies.py", forbidden_imports=FORBIDDEN_POLICY_IMPORTS
        )
        if not _is_allowed_policy_debt(source, imported)
    ]

    assert violations == []


def test_registered_module_routers_do_not_import_orm_models_directly() -> None:
    violations = _violations_for(
        layer_filename="router.py", forbidden_imports=FORBIDDEN_ROUTER_IMPORTS
    )

    assert violations == []


def test_registered_module_repositories_stay_below_api_layers() -> None:
    violations = _violations_for(
        layer_filename="repository.py", forbidden_imports=FORBIDDEN_REPOSITORY_IMPORTS
    )

    assert violations == []


def test_registered_module_jobs_and_enqueue_stay_out_of_transport_and_orm_imports() -> None:
    violations: list[tuple[Path, str]] = []
    for source in [
        *_existing_layer_files("jobs.py"),
        *_existing_layer_files("enqueue.py"),
    ]:
        for imported in _imports(source):
            if any(_matches(imported, forbidden) for forbidden in FORBIDDEN_JOB_IMPORTS):
                violations.append((source, imported))

    assert violations == []


def test_registry_and_module_metadata_stay_runtime_free() -> None:
    violations: list[tuple[Path, str]] = []
    for source in [MODULES_ROOT / "registry.py", *_existing_layer_files("module.py")]:
        for imported in _imports(source):
            if any(_matches(imported, forbidden) for forbidden in FORBIDDEN_METADATA_IMPORTS):
                violations.append((source, imported))

    assert violations == []


def test_registered_workflow_handlers_are_owned_by_registered_module_jobs() -> None:
    module_names = {module.name for module in iter_modules()}
    violations: list[str] = []
    for workflow in iter_workflows():
        handler_module, _, handler_name = workflow.handler_path.partition(":")
        parts = handler_module.split(".")
        if (
            len(parts) != 4
            or parts[:2] != ["app", "modules"]
            or parts[2] not in module_names
            or parts[3] != "jobs"
            or not handler_name
        ):
            violations.append(workflow.handler_path)

    assert violations == []


def test_layer_debt_exceptions_have_existing_sources() -> None:
    missing = [
        str(exception.source)
        for exception in POLICY_LAYER_DEBT_EXCEPTIONS
        if not exception.source.exists()
    ]

    assert missing == []
