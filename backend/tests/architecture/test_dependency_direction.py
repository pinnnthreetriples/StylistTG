from __future__ import annotations

import ast
from collections import defaultdict
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
API_IMPORT_ALLOWLIST = {
    APP_ROOT / "modules" / "account_core" / "accounts_router.py",
    APP_ROOT / "modules" / "account_core" / "compat_router.py",
    APP_ROOT / "modules" / "account_safety" / "accounts_router.py",
    APP_ROOT / "modules" / "account_safety" / "quarantine_router.py",
    APP_ROOT / "modules" / "account_safety" / "runtime_router.py",
    APP_ROOT / "modules" / "account_safety" / "status_router.py",
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


def _feature_module_for(path: Path) -> str | None:
    parts = path.parts
    try:
        index = parts.index("modules")
    except ValueError:
        return None
    if len(parts) <= index + 1:
        return None
    module = parts[index + 1]
    if module in {"contracts", "registry"}:
        return None
    return module


def test_domain_layers_do_not_import_api_layer() -> None:
    violations: list[str] = []
    for root in DOMAIN_ROOTS:
        for source in _python_files(root):
            if source in API_IMPORT_ALLOWLIST:
                continue
            if "modules" in source.parts and source.name == "router.py":
                continue
            for imported in _imports(source):
                if imported == "app.api" or imported.startswith("app.api."):
                    violations.append(
                        "\n".join(
                            [
                                "Illegal inward API dependency detected:",
                                f"Source: {_module_name(source)}",
                                f"Imported: {imported}",
                                "Expected: API routers depend on domain/service layers, not the reverse.",
                            ]
                        )
                    )

    assert violations == []


def test_feature_module_dependency_graph_has_no_cycles() -> None:
    # Documented cyclic groups that are intentionally accepted as
    # architectural debt. Each frozenset is the unique set of modules that
    # form a cycle; any cycle whose visited modules exactly match one of
    # these sets is allowlisted.
    DOCUMENTED_CYCLE_EXCEPTIONS = {
        # account_core owns canonical account lookup (lookup_account,
        # build_account_capabilities, list_workspace_accounts).
        # account_safety imports those from account_core.interfaces. In
        # return, account_core's compat router proxies the safety runtime
        # endpoints. account_core's account list endpoint also calls
        # warmup.service.batch_active_warmups_for_accounts to compose
        # warmup status into the response. warmup, in turn, consults the
        # safety gate for action decisions. The resulting
        # account_core ↔ account_safety pair and the
        # account_core ↔ warmup ↔ account_safety triangle are accepted
        # debt; extracting a shared lookup/composition primitive to break
        # the cycles is tracked for a follow-up PR.
        frozenset({"account_core", "account_safety"}),
        frozenset({"account_core", "warmup", "account_safety"}),
    }

    graph: dict[str, set[str]] = defaultdict(set)
    modules = {
        path.name
        for path in (APP_ROOT / "modules").iterdir()
        if path.is_dir() and not path.name.startswith("__")
    }
    modules -= {"contracts", "registry"}

    for source in _python_files(APP_ROOT / "modules"):
        source_module = _feature_module_for(source)
        if source_module is None:
            continue
        for imported in _imports(source):
            prefix = "app.modules."
            if not imported.startswith(prefix):
                continue
            imported_module = imported[len(prefix) :].split(".", 1)[0]
            if imported_module in modules and imported_module != source_module:
                graph[source_module].add(imported_module)

    cycles: list[str] = []

    def visit(module: str, stack: tuple[str, ...]) -> None:
        if module in stack:
            cycle_modules = stack[stack.index(module) :] + (module,)
            if frozenset(cycle_modules) in DOCUMENTED_CYCLE_EXCEPTIONS:
                return
            cycles.append(" -> ".join(cycle_modules))
            return
        for dependency in graph.get(module, set()):
            visit(dependency, (*stack, module))

    for module in modules:
        visit(module, ())

    assert cycles == []


def test_repositories_do_not_import_fastapi_or_api_layer() -> None:
    violations: list[str] = []
    for source in [
        *APP_ROOT.rglob("*repository*.py"),
        *APP_ROOT.rglob("*repositories*.py"),
    ]:
        if "__pycache__" in source.parts:
            continue
        for imported in _imports(source):
            if (
                imported == "fastapi"
                or imported.startswith("fastapi.")
                or imported.startswith("app.api")
            ):
                violations.append(
                    "\n".join(
                        [
                            "Illegal repository presentation dependency detected:",
                            f"Source: {_module_name(source)}",
                            f"Imported: {imported}",
                            "Expected: repositories stay below FastAPI/API layers.",
                        ]
                    )
                )

    assert violations == []
