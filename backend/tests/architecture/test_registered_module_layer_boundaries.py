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

DECLARED_LAYER_FILES: dict[str, tuple[Path, ...]] = {
    "contracts": (Path("contracts.py"),),
    "policy": (
        Path("policies.py"),
        Path("account_safety/policy_rules.py"),
        Path("neuro_commenting/policies.py"),
        Path("neuro_commenting/rules_policy.py"),
        Path("neuro_commenting/safety_policy.py"),
    ),
    "domain_support": (Path("account_safety/cooldown_rules.py"),),
    "facade": (Path("account_safety/policy.py"),),
    "repository": (
        Path("repository.py"),
        Path("account_safety/policy_repository.py"),
        Path("account_safety/status_repository.py"),
    ),
    "router": (
        Path("router.py"),
        Path("account_core/accounts_router.py"),
        Path("account_core/compat_router.py"),
        Path("account_safety/accounts_router.py"),
        Path("account_safety/policy_router.py"),
        Path("account_safety/quarantine_router.py"),
        Path("story/capabilities_router.py"),
        Path("story/drafts_router.py"),
        Path("story/posts_router.py"),
        Path("account_safety/status_router.py"),
        Path("account_safety/runtime_router.py"),
    ),
    "jobs": (Path("jobs.py"), Path("enqueue.py")),
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


def _declared_layer_files(layer: str) -> list[Path]:
    declared = DECLARED_LAYER_FILES[layer]
    files: list[Path] = []
    for module_root in _registered_module_roots():
        for relative in declared:
            if len(relative.parts) > 1 and relative.parts[0] != module_root.name:
                continue
            source = module_root / (
                Path(*relative.parts[1:]) if len(relative.parts) > 1 else relative
            )
            if source.exists():
                files.append(source)
    return sorted(set(files))


def _violations_for_sources(
    sources: list[Path], forbidden_imports: tuple[str, ...]
) -> list[tuple[Path, str]]:
    violations: list[tuple[Path, str]] = []
    for source in sources:
        for imported in _imports(source):
            if any(_matches(imported, forbidden) for forbidden in forbidden_imports):
                violations.append((source, imported))
    return violations


def _violations_for(*, layer: str, forbidden_imports: tuple[str, ...]) -> list[tuple[Path, str]]:
    return _violations_for_sources(_declared_layer_files(layer), forbidden_imports)


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
    violations = _violations_for(layer="contracts", forbidden_imports=FORBIDDEN_CONTRACT_IMPORTS)

    assert violations == []


def test_registered_module_policies_do_not_add_transport_runtime_or_persistence_imports() -> None:
    violations = [
        (source, imported)
        for source, imported in _violations_for(
            layer="policy", forbidden_imports=FORBIDDEN_POLICY_IMPORTS
        )
        if not _is_allowed_policy_debt(source, imported)
    ]

    assert violations == []


def test_account_safety_policy_facade_stays_reexport_only() -> None:
    source = MODULES_ROOT / "account_safety" / "policy.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    allowed_nodes = (ast.Expr, ast.ImportFrom, ast.Assign)
    violations = [
        type(node).__name__
        for node in tree.body
        if not (
            isinstance(node, allowed_nodes)
            or (isinstance(node, ast.ImportFrom) and node.module == "__future__")
        )
    ]

    assert violations == []


def test_registered_module_routers_do_not_import_orm_models_directly() -> None:
    violations = _violations_for(layer="router", forbidden_imports=FORBIDDEN_ROUTER_IMPORTS)

    assert violations == []


def test_registered_module_repositories_stay_below_api_layers() -> None:
    violations = _violations_for(layer="repository", forbidden_imports=FORBIDDEN_REPOSITORY_IMPORTS)

    assert violations == []


def test_account_safety_policy_repository_uses_workspace_bootstrap_boundary() -> None:
    source = MODULES_ROOT / "account_safety" / "policy_repository.py"
    imports = _imports(source)

    assert "app.workspace_bootstrap.ensure_default_workspace" in imports
    assert not any(imported.startswith("app.services.") for imported in imports)


def test_registered_module_jobs_and_enqueue_stay_out_of_transport_and_orm_imports() -> None:
    violations: list[tuple[Path, str]] = []
    for source in _declared_layer_files("jobs"):
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


def test_account_safety_migrated_routes_are_registered_once() -> None:
    from fastapi.routing import APIRoute

    from app.main import app

    expected_routes = {
        ("GET", "/api/accounts/{account_id}/quarantine"),
        ("POST", "/api/accounts/{account_id}/quarantine/release"),
        ("POST", "/api/accounts/{account_id}/quarantine/admin-override"),
        ("POST", "/api/accounts/{account_id}/terminal-status/clear"),
        ("GET", "/api/accounts/{account_id}/status-observations"),
        ("POST", "/api/accounts/{account_id}/reauth-sessions"),
        ("POST", "/api/accounts/{account_id}/refresh-runtime"),
        ("GET", "/api/accounts/{account_id}/runtime-diagnostics"),
    }
    counts = {route: 0 for route in expected_routes}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            key = (method, route.path)
            if key in counts:
                counts[key] += 1

    assert counts == {route: 1 for route in expected_routes}


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


def test_registered_module_layer_like_files_are_declared() -> None:
    declared = {
        MODULES_ROOT / module.name / relative
        for module in iter_modules()
        for files in DECLARED_LAYER_FILES.values()
        for relative in files
        if len(relative.parts) == 1
    } | {
        MODULES_ROOT / relative
        for files in DECLARED_LAYER_FILES.values()
        for relative in files
        if len(relative.parts) > 1
    }
    discovered = [
        path
        for module_root in _registered_module_roots()
        for path in module_root.glob("*.py")
        if path.name == "router.py"
        or path.name.endswith("_router.py")
        or path.name == "policies.py"
        or path.name.endswith("policy.py")
        or path.name.endswith("_rules.py")
        or path.name.endswith("_repository.py")
    ]

    assert [path for path in discovered if path not in declared] == []


def test_layer_violation_helpers_catch_alternate_router_and_policy_names(
    tmp_path: Path,
) -> None:
    router = tmp_path / "accounts_router.py"
    policy = tmp_path / "rules_policy.py"
    router.write_text("from app.models import Account\n", encoding="utf-8")
    policy.write_text("from sqlalchemy.orm import Session\n", encoding="utf-8")

    assert _violations_for_sources([router], FORBIDDEN_ROUTER_IMPORTS) == [
        (router, "app.models.Account")
    ]
    assert _violations_for_sources([policy], FORBIDDEN_POLICY_IMPORTS) == [
        (policy, "sqlalchemy.orm.Session")
    ]
