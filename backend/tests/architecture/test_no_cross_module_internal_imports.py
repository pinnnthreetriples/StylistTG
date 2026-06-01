from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path


APP_ROOT = Path("app")
MODULES_ROOT = APP_ROOT / "modules"
PUBLIC_FACADE_EXCEPTIONS_PATH = Path("../docs/architecture/public-facade-exceptions.json")
if not PUBLIC_FACADE_EXCEPTIONS_PATH.exists():
    PUBLIC_FACADE_EXCEPTIONS_PATH = Path("docs/architecture/public-facade-exceptions.json")
PUBLIC_SUBMODULES = {
    "contracts",
    "events",
    "interfaces",
}
SHARED_MODULES = {"contracts", "registry"}
ACCOUNT_SAFETY_INTERFACE_SYMBOLS = {
    "SafetyGateReservation",
    "SafetyGateVerdict",
    "build_account_safety_for_account",
    "build_account_readiness_risk",
    "evaluate",
    "release",
    "reserve",
    "safety_preview_fields_with_policy",
    "unique_preserve_order",
}


@dataclass(frozen=True, slots=True)
class CrossModuleFacadeException:
    source: Path
    imported_module: str
    public_name: str
    rationale: str


DOCUMENTED_PUBLIC_FACADE_EXCEPTIONS = {
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_audit" / "router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical account-audit router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_audit" / "router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical account-audit router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_core" / "accounts_router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical account-core accounts router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_core" / "accounts_router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical account-core accounts router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_core" / "accounts_router.py",
        imported_module="warmup",
        public_name="service",
        rationale=(
            "Account-core account list/read models still expose warmup status; remove when warmup "
            "publishes a dedicated account-summary interface."
        ),
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_core" / "compat_router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical account-core compatibility router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_core" / "compat_router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical account-core compatibility router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_imports" / "router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical account-imports router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_imports" / "router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical account-imports router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_jobs" / "router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical account-jobs router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_jobs" / "router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical account-jobs router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_proxy" / "router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical account-proxy router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_proxy" / "router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical account-proxy router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_proxy" / "router.py",
        imported_module="warmup",
        public_name="service",
        rationale=(
            "Account-proxy changes still consult warmup lock policy; remove when warmup exposes "
            "a dedicated operation-lock interface."
        ),
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_editing" / "router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical routers.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "warmup" / "router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical routers.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "neuro_commenting" / "router_common.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical routers.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "neuro_commenting" / "router_common.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical routers.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_safety" / "accounts_router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical account-safety routers.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_safety" / "accounts_router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical account-safety routers.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_safety" / "policy_router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical account-safety policy router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_safety" / "policy_router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical account-safety policy router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_safety" / "quarantine_router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical account-safety quarantine router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_safety" / "quarantine_router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical account-safety quarantine router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_safety" / "runtime_router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical account-safety runtime router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_safety" / "runtime_router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical account-safety runtime router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_safety" / "status_router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical account-safety status router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_safety" / "status_router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical account-safety status router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_lifecycle" / "router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical account-lifecycle router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_lifecycle" / "router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical account-lifecycle router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_profile_completeness" / "router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical account profile-completeness router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_editing" / "service.py",
        imported_module="warmup",
        public_name="service",
        rationale=(
            "Account-editing still asks warmup for warmup-operation lock state; remove when "
            "that lock decision is exposed as a dedicated contracts/interfaces boundary."
        ),
    ),
    # PR3 canonical modules: auth context/dependencies + account_core
    # header helper + account_safety quarantine helpers are accepted
    # facades for routers/services that depend on platform glue.
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_ggr" / "router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical account-ggr router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "account_ggr" / "router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical account-ggr router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "bought_onboarding" / "router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical bought-onboarding router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "bought_onboarding" / "router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical bought-onboarding router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "bought_onboarding" / "service.py",
        imported_module="account_safety",
        public_name="quarantine",
        rationale=(
            "Bought-onboarding orchestrates rest-period quarantine via account_safety; "
            "remove when account_safety exposes a dedicated quarantine interface."
        ),
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "human_behavior" / "router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical human-behavior router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "human_behavior" / "router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical human-behavior router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "story" / "capabilities_router.py",
        imported_module="account_core",
        public_name="context",
        rationale="Canonical account_id_header header dependency used by story routers.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "story" / "capabilities_router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical story-capabilities router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "story" / "capabilities_router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical story-capabilities router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "story" / "drafts_router.py",
        imported_module="account_core",
        public_name="context",
        rationale="Canonical account_id_header header dependency used by story routers.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "story" / "drafts_router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical story-drafts router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "story" / "drafts_router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical story-drafts router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "story" / "posts_router.py",
        imported_module="account_core",
        public_name="context",
        rationale="Canonical account_id_header header dependency used by story routers.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "story" / "posts_router.py",
        imported_module="auth",
        public_name="context",
        rationale="FastAPI auth context facade used by canonical story-posts router.",
    ),
    CrossModuleFacadeException(
        source=MODULES_ROOT / "story" / "posts_router.py",
        imported_module="auth",
        public_name="dependencies",
        rationale="FastAPI auth dependency facade used by canonical story-posts router.",
    ),
}


def _python_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def _module_name(path: Path) -> str:
    return ".".join(path.with_suffix("").parts)


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


def _feature_module_for(path: Path) -> str | None:
    parts = path.parts
    try:
        index = parts.index("modules")
    except ValueError:
        return None
    if len(parts) <= index + 1:
        return None
    if path.parent == MODULES_ROOT:
        return None
    module = parts[index + 1]
    if module in SHARED_MODULES or module == "__pycache__":
        return None
    return module


def _cross_module_public_name(imported: str, source_module: str) -> tuple[str, str] | None:
    prefix = "app.modules."
    if not imported.startswith(prefix):
        return None

    remainder = imported[len(prefix) :]
    imported_module = remainder.split(".", 1)[0]
    if imported_module in SHARED_MODULES or imported_module == source_module:
        return None

    if "." not in remainder:
        return (imported_module, "<package>")

    public_name = remainder.split(".", 2)[1]
    return (imported_module, public_name)


def _is_allowed_cross_module_import(
    *, source: Path, imported_module: str, public_name: str
) -> bool:
    if public_name in PUBLIC_SUBMODULES:
        return True
    return any(
        exception.source == source
        and exception.imported_module == imported_module
        and exception.public_name == public_name
        for exception in DOCUMENTED_PUBLIC_FACADE_EXCEPTIONS
    )


def test_feature_modules_do_not_import_other_module_internals() -> None:
    violations: list[str] = []
    for source in _python_files(MODULES_ROOT):
        source_module = _feature_module_for(source)
        if source_module is None:
            continue
        for imported in _imports(source):
            cross_module = _cross_module_public_name(imported, source_module)
            if cross_module is None:
                continue
            imported_module, public_name = cross_module
            if _is_allowed_cross_module_import(
                source=source, imported_module=imported_module, public_name=public_name
            ):
                continue
            violations.append(
                "\n".join(
                    [
                        "Illegal cross-module internal import detected:",
                        f"Source: {_module_name(source)}",
                        f"Imported: {imported}",
                        f"Public name: {public_name}",
                        "Allowed by default: contracts, events, interfaces.",
                        "Other facades require DOCUMENTED_PUBLIC_FACADE_EXCEPTIONS.",
                    ]
                )
            )

    assert violations == []


def test_account_safety_interface_cross_module_imports_are_allowlisted_symbols() -> None:
    violations: list[str] = []
    prefix = "app.modules.account_safety.interfaces."
    for source in _python_files(MODULES_ROOT):
        source_module = _feature_module_for(source)
        if source_module is None or source_module == "account_safety":
            continue
        for imported in _imports(source):
            if not imported.startswith(prefix):
                continue
            symbol = imported.removeprefix(prefix).split(".", 1)[0]
            if symbol not in ACCOUNT_SAFETY_INTERFACE_SYMBOLS:
                violations.append(f"{_module_name(source)} imports {imported}")

    assert violations == []


def test_documented_public_facade_exceptions_have_rationale_and_existing_source() -> None:
    violations = [
        str(exception)
        for exception in DOCUMENTED_PUBLIC_FACADE_EXCEPTIONS
        if not exception.source.exists()
        or len(exception.rationale) < 20
        or not any(
            imported == f"app.modules.{exception.imported_module}.{exception.public_name}"
            or imported.startswith(
                f"app.modules.{exception.imported_module}.{exception.public_name}."
            )
            for imported in _imports(exception.source)
        )
    ]

    assert violations == []


def test_public_facade_exceptions_doc_matches_allowlist() -> None:
    records = json.loads(PUBLIC_FACADE_EXCEPTIONS_PATH.read_text(encoding="utf-8"))
    assert records["schema_version"] == 1

    expected = {
        (
            (Path("backend") / exception.source).as_posix(),
            exception.imported_module,
            exception.public_name,
            exception.rationale,
        )
        for exception in DOCUMENTED_PUBLIC_FACADE_EXCEPTIONS
    }
    documented = {
        (
            record["source"],
            record["imported_module"],
            record["public_name"],
            record["rationale"],
        )
        for record in records["exceptions"]
    }

    assert documented == expected
    assert all(record["owner"] and record["owner"] != "unknown" for record in records["exceptions"])
    assert all(len(record.get("removal_condition", "")) >= 3 for record in records["exceptions"])


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


def test_account_safety_package_exposes_narrow_public_boundary() -> None:
    init_file = MODULES_ROOT / "account_safety" / "__init__.py"
    tree = ast.parse(init_file.read_text(encoding="utf-8"), filename=str(init_file))
    public_exports: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        ):
            continue
        if not isinstance(node.value, ast.List):
            continue
        public_exports = [
            item.value
            for item in node.value.elts
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        ]

    assert public_exports == ["contracts", "interfaces", "module"]
