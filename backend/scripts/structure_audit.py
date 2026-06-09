from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legacy_wrapper_audit import WRAPPERS as LEGACY_WRAPPERS

_AST_PARSE_ERRORS = (SyntaxError, UnicodeDecodeError)
REPORT_SCHEMA_VERSION = 2

MODULES_ROOT = Path("backend/app/modules")
CONTRACTS_ROOT = Path("backend/app/contracts")
RUNTIME_ROOT = Path("backend/app/runtime")
FRONTEND_MODULES_ROOT = Path("apps/dashboard/src/modules")
FRONTEND_APP_ROOT = Path("apps/dashboard/src")
FRONTEND_BOUNDARY_POLICY_PATH = Path("docs/architecture/frontend-boundary-policy.json")
DEFAULT_JSON_OUTPUT = Path("docs/architecture/structure-audit.json")
DEFAULT_MARKDOWN_OUTPUT = Path("docs/architecture/STRUCTURE_AUDIT.md")
DEFAULT_DEBT_OUTPUT = Path("docs/architecture/architecture-debt-inventory.json")
PUBLIC_FACADE_EXCEPTIONS_PATH = Path("docs/architecture/public-facade-exceptions.json")
RESIDUAL_BOUNDARY_GUARD_PATH = Path("docs/architecture/residual-legacy-boundaries.json")
RESIDUAL_BOUNDARY_CATEGORY = "residual_legacy_feature_boundary"

WRAPPER_PATHS = tuple(spec.file for spec in LEGACY_WRAPPERS)

FORBIDDEN_CONTRACT_IMPORTS = (
    "app.models",
    "sqlalchemy",
    "fastapi",
    "redis",
    "rq",
    "app.adapters.tdlib",
    "app.adapters.warmup_tdlib",
)
FORBIDDEN_POLICY_IMPORTS = (
    "app.models",
    "sqlalchemy",
    "app.db",
    "app.api",
    "fastapi",
    "redis",
    "rq",
)
FORBIDDEN_REPOSITORY_IMPORTS = ("fastapi", "app.api", "app.main")
TS_IMPORT_SPECIFIER_RE = re.compile(
    r"(?:\bimport\s*\(\s*['\"]([^'\"]+)['\"]\s*\)|"
    r"\b(?:import|export)\s+(?:type\s+)?(?:[\s\S]*?\s+from\s+)?['\"]([^'\"]+)['\"])",
    flags=re.MULTILINE,
)

DECLARED_LAYER_FILES: dict[str, tuple[Path, ...]] = {
    "policy": (
        Path("policies.py"),
        Path("account_safety/policy_rules.py"),
        Path("neuro_commenting/policies.py"),
        Path("neuro_commenting/rules_policy.py"),
        Path("neuro_commenting/safety_policy.py"),
    ),
    "repository": (
        Path("repository.py"),
        Path("account_safety/policy_repository.py"),
    ),
    "router": (
        Path("router.py"),
        Path("account_safety/accounts_router.py"),
        Path("account_safety/policy_router.py"),
    ),
}


@dataclass(frozen=True)
class Finding:
    id: str
    severity: str
    status: str
    area: str
    finding: str
    evidence: str
    risk: str
    recommendation: str
    suggested_phase: str


@dataclass(frozen=True)
class OwnershipEntry:
    id: str
    category: str
    severity: str
    status: str
    owner: str
    paths: tuple[str, ...]
    target_owner: str
    phase: str
    removal_condition: str
    rationale: str


OWNERSHIP_ENTRIES: tuple[OwnershipEntry, ...] = (
    OwnershipEntry(
        id="canonical-auth",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="auth",
        paths=("backend/app/modules/auth/**",),
        target_owner="app.modules.auth",
        phase="complete",
        removal_condition="n/a",
        rationale="Authentication context and policy ownership is canonical.",
    ),
    OwnershipEntry(
        id="canonical-account-editing",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="account_editing",
        paths=("backend/app/modules/account_editing/**",),
        target_owner="app.modules.account_editing",
        phase="complete",
        removal_condition="n/a",
        rationale="Account editing runtime ownership is canonical.",
    ),
    OwnershipEntry(
        id="canonical-warmup",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="warmup",
        paths=("backend/app/modules/warmup/**",),
        target_owner="app.modules.warmup",
        phase="complete",
        removal_condition="n/a",
        rationale="Warmup/account-preparation ownership is canonical.",
    ),
    OwnershipEntry(
        id="canonical-neuro-commenting",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="neuro_commenting",
        paths=("backend/app/modules/neuro_commenting/**",),
        target_owner="app.modules.neuro_commenting",
        phase="Phase 2D",
        removal_condition="n/a",
        rationale="Neuro-commenting router, contracts, workflow metadata, and public facades are canonical.",
    ),
    OwnershipEntry(
        id="canonical-account-safety",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="account_safety",
        paths=("backend/app/modules/account_safety/**",),
        target_owner="app.modules.account_safety",
        phase="Phase 3B",
        removal_condition="n/a",
        rationale="Account-safety routers, read models, gate/cache/reserve/override/policy services, and contracts are canonical; old API/service/contract paths are compatibility wrappers.",
    ),
    OwnershipEntry(
        id="canonical-account-lifecycle",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="account_lifecycle",
        paths=("backend/app/modules/account_lifecycle/**",),
        target_owner="app.modules.account_lifecycle",
        phase="Phase 4",
        removal_condition="n/a",
        rationale="Account lifecycle router, deletion/export services, retention worker, and contracts are canonical; old API/service paths are compatibility wrappers.",
    ),
    OwnershipEntry(
        id="canonical-account-survival",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="account_survival",
        paths=("backend/app/modules/account_survival/**",),
        target_owner="app.modules.account_survival",
        phase="Phase 6A",
        removal_condition="n/a",
        rationale="Account survival router, queries, repository, and contracts are canonical.",
    ),
    OwnershipEntry(
        id="canonical-account-profile-completeness",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="account_profile_completeness",
        paths=("backend/app/modules/account_profile_completeness/**",),
        target_owner="app.modules.account_profile_completeness",
        phase="Phase 6A",
        removal_condition="n/a",
        rationale="Account profile-completeness route, service, and contract ownership is canonical; old API/service/contract paths are compatibility wrappers.",
    ),
    OwnershipEntry(
        id="canonical-account-audit",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="account_audit",
        paths=("backend/app/modules/account_audit/**",),
        target_owner="app.modules.account_audit",
        phase="PR2",
        removal_condition="n/a",
        rationale="Account audit transport ownership is canonical; old API path is a compatibility wrapper.",
    ),
    OwnershipEntry(
        id="canonical-account-core",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="account_core",
        paths=("backend/app/modules/account_core/**",),
        target_owner="app.modules.account_core",
        phase="PR2",
        removal_condition="n/a",
        rationale="Core account CRUD, compatibility routes, context, bundle, capabilities, and DTO ownership is canonical; old API/service/contract paths are compatibility wrappers.",
    ),
    OwnershipEntry(
        id="canonical-account-shared",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="account_shared",
        paths=("backend/app/modules/account_shared/**",),
        target_owner="app.modules.account_shared",
        phase="PR4",
        removal_condition="n/a",
        rationale="Neutral shared primitives (account lookup, capabilities, runtime composition) used by account_core, account_safety, warmup, and other feature modules without forming cross-module cycles.",
    ),
    OwnershipEntry(
        id="canonical-account-imports",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="account_imports",
        paths=("backend/app/modules/account_imports/**",),
        target_owner="app.modules.account_imports",
        phase="PR2",
        removal_condition="n/a",
        rationale="Account import route and service ownership is canonical; old API/service paths are compatibility wrappers.",
    ),
    OwnershipEntry(
        id="canonical-account-onboarding",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="account_onboarding",
        paths=("backend/app/modules/account_onboarding/**",),
        target_owner="app.modules.account_onboarding",
        phase="PR291",
        removal_condition="n/a",
        rationale="Account onboarding route, service, adapters, private artifacts, and workflow metadata ownership is canonical.",
    ),
    OwnershipEntry(
        id="canonical-account-jobs",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="account_jobs",
        paths=("backend/app/modules/account_jobs/**",),
        target_owner="app.modules.account_jobs",
        phase="PR2",
        removal_condition="n/a",
        rationale="Account jobs route and interface ownership is canonical; old API path is a compatibility wrapper.",
    ),
    OwnershipEntry(
        id="canonical-account-proxy",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="account_proxy",
        paths=("backend/app/modules/account_proxy/**",),
        target_owner="app.modules.account_proxy",
        phase="PR2",
        removal_condition="n/a",
        rationale="Account proxy route, assignment service, and check service ownership is canonical; old API/service paths are compatibility wrappers.",
    ),
    OwnershipEntry(
        id="module-registry-and-template",
        category="shared_platform_infrastructure",
        severity="info",
        status="accepted",
        owner="modules-platform",
        paths=(
            "backend/app/modules/__init__.py",
            "backend/app/modules/contracts.py",
            "backend/app/modules/registry.py",
            "backend/app/modules/_template/**",
        ),
        target_owner="app.modules",
        phase="ongoing",
        removal_condition="n/a",
        rationale="Module metadata, registry, and non-runtime template support module governance.",
    ),
    OwnershipEntry(
        id="canonical-account-ggr",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="account_ggr",
        paths=("backend/app/modules/account_ggr/**",),
        target_owner="app.modules.account_ggr",
        phase="PR3",
        removal_condition="n/a",
        rationale="GGR composite scoring and fraud-score provider ownership is canonical; old API/service/contract paths are compatibility wrappers.",
    ),
    OwnershipEntry(
        id="canonical-account-profile-state",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="account_profile_state",
        paths=("backend/app/modules/account_profile_state/**",),
        target_owner="app.modules.account_profile_state",
        phase="PR3",
        removal_condition="n/a",
        rationale="Profile audio/photo helpers and profile-sync adapter ownership is canonical; old service paths are compatibility wrappers.",
    ),
    OwnershipEntry(
        id="canonical-bought-onboarding",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="bought_onboarding",
        paths=("backend/app/modules/bought_onboarding/**",),
        target_owner="app.modules.bought_onboarding",
        phase="PR3",
        removal_condition="n/a",
        rationale="Bought-account onboarding orchestration, router, and DTO ownership is canonical; old API/service/contract paths are compatibility wrappers.",
    ),
    OwnershipEntry(
        id="canonical-human-behavior",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="human_behavior",
        paths=("backend/app/modules/human_behavior/**",),
        target_owner="app.modules.human_behavior",
        phase="PR3",
        removal_condition="n/a",
        rationale="Human-behavior baseline, randomization, typing/typo/decoy emulators, and sequencer ownership is canonical; old API/service/contract paths are compatibility wrappers.",
    ),
    OwnershipEntry(
        id="canonical-story",
        category="canonical_feature_module",
        severity="info",
        status="accepted",
        owner="story",
        paths=("backend/app/modules/story/**",),
        target_owner="app.modules.story",
        phase="PR3",
        removal_condition="n/a",
        rationale="Story capabilities, draft, and post routers + services ownership is canonical; old API/service paths are compatibility wrappers.",
    ),
    OwnershipEntry(
        id="compatibility-wrappers",
        category="compatibility_wrapper",
        severity="low",
        status="accepted",
        owner="compatibility",
        paths=tuple(WRAPPER_PATHS),
        target_owner="documented canonical module owners",
        phase="wrapper-cleanup",
        removal_condition="Remove only after import/reference audit proves no downstream users and replacement paths are stable.",
        rationale="Known wrappers preserve public import compatibility and must remain behavior-free.",
    ),
    OwnershipEntry(
        id="runtime-process-ownership",
        category="runtime_process_ownership",
        severity="info",
        status="accepted",
        owner="runtime",
        paths=(
            "backend/app/runtime/**",
            "backend/app/workers/__init__.py",
            "backend/app/workers/auth_batch_jobs.py",
            "backend/app/workers/profile_child_events.py",
            "backend/app/workers/profile_child_results.py",
            "backend/app/workers/profile_jobs.py",
            "backend/app/workers/run_worker.py",
            "backend/app/workers/telegram_auth_jobs.py",
            "backend/app/job_queue/**",
            "backend/app/services/worker_plane.py",
            "backend/app/services/scheduler.py",
            "backend/app/services/stale_jobs.py",
            "backend/app/services/production_reaper.py",
            "backend/app/services/reconcile_stuck_attempts.py",
        ),
        target_owner="runtime roles and workflow registry",
        phase="ongoing",
        removal_condition="n/a",
        rationale="Worker processes, queue declarations, and scheduling/reaper paths are execution infrastructure.",
    ),
    OwnershipEntry(
        id="shared-platform-infrastructure",
        category="shared_platform_infrastructure",
        severity="info",
        status="accepted",
        owner="platform",
        paths=(
            "backend/app/__init__.py",
            "backend/app/config.py",
            "backend/app/db.py",
            "backend/app/errors.py",
            "backend/app/logging_utils.py",
            "backend/app/main.py",
            "backend/app/openapi_document.py",
            "backend/app/platform_bootstrap.py",
            "backend/app/tdlib_job.py",
            "backend/app/workspace_bootstrap.py",
            "backend/app/adapters/**",
            "backend/app/storage/**",
            "backend/app/observability/__init__.py",
            "backend/app/observability/safety_metrics.py",
            "backend/app/observability/sentry.py",
            "backend/app/scripts/**",
            "backend/app/tools/**",
            "backend/app/api/__init__.py",
            "backend/app/api/auth.py",
            "backend/app/api/auth_batch_support.py",
            "backend/app/api/auth_batches.py",
            "backend/app/api/audit.py",
            "backend/app/api/assets.py",
            "backend/app/api/dashboard.py",
            "backend/app/api/diagnostics.py",
            "backend/app/api/jobs.py",
            "backend/app/api/me.py",
            "backend/app/api/operation_logs.py",
            "backend/app/api/settings.py",
            "backend/app/api/tdlib_runtime.py",
            "backend/app/api/telegram_auth.py",
            "backend/app/api/tenant_helpers.py",
            "backend/app/api/workers.py",
            "backend/app/api/workspace_feature_flags_routes.py",
            "backend/app/services/admin_notifications.py",
            "backend/app/services/asset_cleanup.py",
            "backend/app/services/asset_storage.py",
            "backend/app/services/asset_validation.py",
            "backend/app/services/assets.py",
            "backend/app/services/audit_logs.py",
            "backend/app/services/auth.py",
            "backend/app/services/auth_batch_dispatcher.py",
            "backend/app/services/auth_batch_errors.py",
            "backend/app/services/auth_batch_recovery.py",
            "backend/app/services/auth_batch_state.py",
            "backend/app/services/auth_batch_tdlib.py",
            "backend/app/services/auth_batches.py",
            "backend/app/services/cross_module_load_tracker.py",
            "backend/app/services/dashboard.py",
            "backend/app/services/database.py",
            "backend/app/services/disaster_state.py",
            "backend/app/services/execution_policy.py",
            "backend/app/services/feature_flags.py",
            "backend/app/services/frontend_diagnostics.py",
            "backend/app/services/idempotency_keys.py",
            "backend/app/services/import_validation.py",
            "backend/app/services/jobs.py",
            "backend/app/services/journal.py",
            "backend/app/services/limits.py",
            "backend/app/services/live_preflight.py",
            "backend/app/services/locks.py",
            "backend/app/services/notification_channels/**",
            "backend/app/services/operation_logs.py",
            "backend/app/services/phone_hints.py",
            "backend/app/services/plan.py",
            "backend/app/services/rate_limit_persistence.py",
            "backend/app/services/rate_limits.py",
            "backend/app/services/recovery.py",
            "backend/app/services/redis_client.py",
            "backend/app/services/retry_policy.py",
            "backend/app/services/runtime_diagnostics.py",
            "backend/app/services/runtime_settings.py",
            "backend/app/services/secret_redaction.py",
            "backend/app/services/sensitive_audit.py",
            "backend/app/services/step_policy.py",
            "backend/app/services/step_registry.py",
            "backend/app/services/supabase_jwt.py",
            "backend/app/services/tdlib*.py",
            "backend/app/services/telegram_auth_sessions.py",
            "backend/app/services/tenant_scope.py",
            "backend/app/services/url_safety.py",
            "backend/app/services/__init__.py",
            "backend/app/services/users.py",
            "backend/app/services/workspace_onboarding.py",
        ),
        target_owner="shared platform/infrastructure",
        phase="ongoing",
        removal_condition="n/a",
        rationale="Cross-cutting auth, storage, runtime, audit, notification, tenant, and operator support code is not a bounded feature module by itself.",
    ),
    OwnershipEntry(
        id="shared-contracts-and-orm",
        category="shared_platform_infrastructure",
        severity="medium",
        status="accepted",
        owner="shared_contracts_storage",
        paths=(
            "backend/app/contracts/__init__.py",
            "backend/app/contracts/disaster_state.py",
            "backend/app/contracts/jobs.py",
            "backend/app/contracts/neuro_commenting.py",
            "backend/app/contracts/neuro_commenting_campaigns.py",
            "backend/app/contracts/neuro_commenting_comments.py",
            "backend/app/contracts/neuro_commenting_common.py",
            "backend/app/contracts/neuro_commenting_metrics.py",
            "backend/app/contracts/neuro_commenting_targets.py",
            "backend/app/contracts/notifications.py",
            "backend/app/contracts/queues.py",
            "backend/app/contracts/types.py",
            "backend/app/migration_helpers/**",
            "backend/app/model_defs/**",
            "backend/app/models.py",
            "backend/app/schema_defs/**",
            "backend/app/schemas.py",
        ),
        target_owner="shared contracts plus repositories/module-owned DTOs",
        phase="Phase 6B",
        removal_condition="Promote DTOs to module contracts only when behavior changes; keep shared contracts and ORM guarded by boundary tests meanwhile.",
        rationale="Global schemas, shared contracts, and ORM models are accepted platform/storage boundaries for the modular monolith; contracts purity and router ORM checks keep them from growing unguarded feature ownership.",
    ),
    OwnershipEntry(
        id="supporting-governance-evidence",
        category="supporting_tool_test_documentation_frontend_evidence",
        severity="info",
        status="accepted",
        owner="architecture-governance",
        paths=(
            "backend/scripts/**",
            "backend/tests/**",
            "docs/**",
            "README.md",
            ".mex/**",
            "apps/dashboard/src/**",
        ),
        target_owner="governance/evidence/frontend ownership",
        phase="ongoing",
        removal_condition="n/a",
        rationale="Supporting audit, tests, docs, memory, and frontend ownership evidence are tracked separately from backend production domains.",
    ),
)


def _read_text(repo_root: Path, relative_path: str) -> str:
    path = repo_root / relative_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _relative(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _utc_timestamp(now: datetime | None = None) -> str:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _entry_to_dict(entry: OwnershipEntry, repo_root: Path) -> dict[str, Any]:
    existing_paths: list[str] = []
    for pattern in entry.paths:
        if any(character in pattern for character in "*?["):
            existing_paths.extend(
                _relative(path, repo_root)
                for path in sorted(repo_root.glob(pattern))
                if path.is_file() and "__pycache__" not in path.parts
            )
            continue
        path = repo_root / pattern
        if path.exists():
            existing_paths.append(_relative(path, repo_root))
    return {
        **asdict(entry),
        "paths": list(entry.paths),
        "existing_paths": sorted(set(existing_paths)),
    }


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _parse_ast(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except _AST_PARSE_ERRORS:
        return None


def _import_names(path: Path) -> list[str]:
    tree = _parse_ast(path)
    if tree is None:
        return []
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return sorted(imports)


def _imported_paths(path: Path) -> list[str]:
    tree = _parse_ast(path)
    if tree is None:
        return []
    imported_paths: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_paths.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_paths.add(node.module)
            imported_paths.update(f"{node.module}.{alias.name}" for alias in node.names)
    return sorted(imported_paths)


def _literal_route_methods(node: ast.AST | None) -> list[str]:
    if node is None:
        return []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value.upper()]
    if isinstance(node, (ast.List, ast.Tuple)):
        return sorted(
            item.value.upper()
            for item in node.elts
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        )
    return []


def _route_fingerprints_for_function(
    relative_path: str,
    node: ast.AsyncFunctionDef | ast.FunctionDef,
) -> list[str]:
    routes: list[str] = []
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            continue
        method = decorator.func.attr.lower()
        route_path = (
            decorator.args[0].value
            if decorator.args
            and isinstance(decorator.args[0], ast.Constant)
            and isinstance(decorator.args[0].value, str)
            else None
        )
        if method == "api_route":
            methods = []
            for keyword in decorator.keywords:
                if keyword.arg == "methods":
                    methods = _literal_route_methods(keyword.value)
                    break
            for api_method in methods or ["API_ROUTE"]:
                if route_path:
                    routes.append(f"{relative_path}:route:{api_method} {route_path} -> {node.name}")
            continue
        if method in {"delete", "get", "patch", "post", "put"} and route_path:
            routes.append(f"{relative_path}:route:{method.upper()} {route_path} -> {node.name}")
    return routes


def _public_api_fingerprint(repo_root: Path, relative_paths: list[str]) -> list[str]:
    fingerprints: list[str] = []
    for relative_path in sorted(relative_paths):
        path = repo_root / relative_path
        tree = _parse_ast(path)
        if tree is None:
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                fingerprints.append(f"{relative_path}:class:{node.name}")
            elif isinstance(
                node, (ast.AsyncFunctionDef, ast.FunctionDef)
            ) and not node.name.startswith("_"):
                fingerprints.append(f"{relative_path}:function:{node.name}")
                fingerprints.extend(_route_fingerprints_for_function(relative_path, node))
    return sorted(set(fingerprints))


def _has_import_prefix(path: Path, forbidden: tuple[str, ...]) -> list[str]:
    matches: list[str] = []
    for imported in _import_names(path):
        for forbidden_import in forbidden:
            if imported == forbidden_import or imported.startswith(f"{forbidden_import}."):
                matches.append(imported)
    return sorted(set(matches))


def _has_all_dunder(path: Path) -> bool:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return "__all__" in text


def _declared_layer_files(repo_root: Path, module_name: str, layer: str) -> list[Path]:
    module_root = repo_root / MODULES_ROOT / module_name
    files: list[Path] = []
    for relative in DECLARED_LAYER_FILES[layer]:
        if len(relative.parts) > 1 and relative.parts[0] != module_name:
            continue
        source = module_root / (Path(*relative.parts[1:]) if len(relative.parts) > 1 else relative)
        if source.exists():
            files.append(source)
    return sorted(files)


def _declared_layer_files_for_all_modules(repo_root: Path, layer: str) -> list[Path]:
    modules_root = repo_root / MODULES_ROOT
    if not modules_root.exists():
        return []
    files: list[Path] = []
    for module_dir in sorted(path for path in modules_root.iterdir() if path.is_dir()):
        files.extend(_declared_layer_files(repo_root, module_dir.name, layer))
    return sorted(files)


def _literal_value(node: ast.AST, constants: dict[str, str]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        owner = _literal_value(node.value, constants)
        if owner == "WorkflowArgsMode":
            return node.attr
        return f"{owner}.{node.attr}" if owner else node.attr
    if isinstance(node, (ast.Tuple, ast.List)):
        return tuple(_literal_value(element, constants) for element in node.elts)
    return None


def _string_assignments(path: Path) -> dict[str, str]:
    tree = _parse_ast(path)
    if tree is None:
        return {}
    assignments: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value.value
    return assignments


def _workflow_specs(repo_root: Path) -> list[dict[str, Any]]:
    constants = _string_assignments(repo_root / "backend/app/contracts/queues.py")
    workflows: list[dict[str, Any]] = []
    for module_file in sorted((repo_root / MODULES_ROOT).glob("*/module.py")):
        tree = _parse_ast(module_file)
        if tree is None:
            continue
        module_name = module_file.parent.name
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_name = getattr(node.func, "id", "")
            if func_name != "WorkflowSpec":
                continue
            spec: dict[str, Any] = {"module": module_name}
            for keyword in node.keywords:
                if keyword.arg in {
                    "workflow_type",
                    "queue_name",
                    "handler_path",
                    "description",
                    "args_mode",
                }:
                    spec[keyword.arg] = _literal_value(keyword.value, constants)
            workflows.append(spec)
    return sorted(workflows, key=lambda item: (item["module"], str(item.get("workflow_type"))))


def _registered_modules(repo_root: Path) -> list[str]:
    registry_text = _read_text(repo_root, "backend/app/modules/registry.py")
    return sorted(set(re.findall(r"from app\.modules\.([a-z_]+)\.module import", registry_text)))


def _module_tests_present(repo_root: Path, module_name: str) -> bool:
    tests_root = repo_root / "backend/tests/modules"
    module_dir = tests_root / module_name
    if module_dir.exists():
        for path in module_dir.rglob("*.py"):
            if "__pycache__" not in path.parts:
                return True
    return any(tests_root.glob(f"test_{module_name}*.py"))


def _audit_modules(repo_root: Path) -> list[dict[str, Any]]:
    modules_root = repo_root / MODULES_ROOT
    registered = set(_registered_modules(repo_root))
    workflows_by_module: dict[str, list[dict[str, Any]]] = {}
    for workflow in _workflow_specs(repo_root):
        workflows_by_module.setdefault(str(workflow["module"]), []).append(workflow)

    modules: list[dict[str, Any]] = []
    if not modules_root.exists():
        return modules

    for module_dir in sorted(
        path
        for path in modules_root.iterdir()
        if path.is_dir()
        and path.name != "__pycache__"
        and any(child.name != "__pycache__" for child in path.iterdir())
    ):
        module_name = module_dir.name
        files = sorted(
            _relative(path, repo_root)
            for path in module_dir.iterdir()
            if path.is_file() and path.name != "__pycache__"
        )
        init_path = module_dir / "__init__.py"
        module_py = module_dir / "module.py"
        router_text = module_py.read_text(encoding="utf-8") if module_py.exists() else ""
        router_path_match = re.search(r'router_path="([^"]+)"', router_text)
        documentation_only = module_name.startswith("_")
        allowed_template_suffixes = (".template", ".md")
        modules.append(
            {
                "name": module_name,
                "documentation_only": documentation_only,
                "files": files,
                "has_init": init_path.exists(),
                "has_explicit_all": _has_all_dunder(init_path) if init_path.exists() else False,
                "has_contracts": (module_dir / "contracts.py").exists(),
                "has_router": bool(_declared_layer_files(repo_root, module_name, "router")),
                "has_service_facade": (module_dir / "service.py").exists(),
                "has_repository": bool(_declared_layer_files(repo_root, module_name, "repository")),
                "has_policies": bool(_declared_layer_files(repo_root, module_name, "policy")),
                "has_errors": (module_dir / "errors.py").exists(),
                "has_jobs": (module_dir / "jobs.py").exists(),
                "has_enqueue": (module_dir / "enqueue.py").exists(),
                "registered": module_name in registered,
                "router_path": router_path_match.group(1) if router_path_match else None,
                "workflows": workflows_by_module.get(module_name, []),
                "tests_present": _module_tests_present(repo_root, module_name),
                "template_files_are_non_runtime": (
                    all(
                        path.name == "README.md" or path.name.endswith(allowed_template_suffixes)
                        for path in module_dir.iterdir()
                    )
                    if documentation_only
                    else None
                ),
            }
        )
    return modules


def _audit_runtime_roles(repo_root: Path) -> list[dict[str, Any]]:
    worker_constants = _string_assignments(repo_root / "backend/app/contracts/queues.py")
    roles_path = repo_root / "backend/app/runtime/roles.py"
    tree = _parse_ast(roles_path)
    roles: list[dict[str, Any]] = []
    if tree is None:
        return roles
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "id", "") != "RuntimeRole":
            continue
        role: dict[str, Any] = {}
        for keyword in node.keywords:
            if keyword.arg is None:
                continue
            value = _literal_value(keyword.value, worker_constants)
            if isinstance(value, tuple):
                value = sorted(str(item) for item in value)
            role[keyword.arg] = value
        roles.append(role)
    return sorted(roles, key=lambda role: str(role.get("name")))


def _audit_queues(repo_root: Path, runtime_roles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    constants = _string_assignments(repo_root / "backend/app/contracts/queues.py")
    production_queues = sorted(
        value for key, value in constants.items() if key.endswith("_QUEUE_NAME")
    )
    covered_by: dict[str, list[str]] = {queue: [] for queue in production_queues}
    for role in runtime_roles:
        for queue in role.get("queues", []):
            covered_by.setdefault(str(queue), []).append(str(role.get("name")))
    return [
        {
            "name": queue,
            "covered_by_roles": sorted(covered_by.get(queue, [])),
            "is_production_queue": queue in production_queues,
        }
        for queue in sorted(covered_by)
    ]


def _module_import_references(repo_root: Path, import_path: str) -> list[str]:
    references: list[str] = []
    modules_root = repo_root / MODULES_ROOT
    for path in _python_files(modules_root):
        imported_paths = _imported_paths(path)
        if any(
            imported == import_path or imported.startswith(f"{import_path}.")
            for imported in imported_paths
        ):
            references.append(_relative(path, repo_root))
    return sorted(references)


def _audit_legacy_wrappers(repo_root: Path) -> list[dict[str, Any]]:
    audit_doc = _read_text(repo_root, "docs/architecture/legacy-wrapper-audit.md")
    manifest_text = _read_text(repo_root, "docs/architecture/legacy-wrappers.json")
    wrappers: list[dict[str, Any]] = []
    for spec in LEGACY_WRAPPERS:
        wrapper = spec.file
        path = repo_root / wrapper
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        canonical_match = re.search(r"Canonical owner:\s*([^\n]+)", text)
        import_path = spec.legacy_path
        wrappers.append(
            {
                "path": wrapper,
                "import_path": import_path,
                "exists": path.exists(),
                "docstring_present": '"""Compatibility wrapper.' in text,
                "canonical_owner": canonical_match.group(1).strip() if canonical_match else None,
                "do_not_add_behavior_marker": "Do not add new behavior here." in text,
                "documented_in_audit": import_path in audit_doc or wrapper in audit_doc,
                "documented_in_manifest": import_path in manifest_text or wrapper in manifest_text,
                "module_import_references": _module_import_references(repo_root, import_path),
            }
        )
    return wrappers


def _audit_shared_contracts(repo_root: Path) -> list[dict[str, Any]]:
    contracts_root = repo_root / CONTRACTS_ROOT
    contracts: list[dict[str, Any]] = []
    if not contracts_root.exists():
        return contracts
    for path in _python_files(contracts_root):
        contracts.append(
            {
                "path": _relative(path, repo_root),
                "imports": _import_names(path),
                "forbidden_imports": _has_import_prefix(path, FORBIDDEN_CONTRACT_IMPORTS),
                "has_explicit_all": _has_all_dunder(path),
            }
        )
    return contracts


def _audit_architecture_tests(repo_root: Path) -> list[dict[str, Any]]:
    tests_root = repo_root / "backend/tests/architecture"
    tests: list[dict[str, Any]] = []
    for path in sorted(tests_root.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        tests.append(
            {
                "path": _relative(path, repo_root),
                "test_count": len(re.findall(r"^def test_", text, flags=re.MULTILINE)),
                "mentions_ast": "ast." in text or "import ast" in text,
                "boundary_keywords": sorted(
                    keyword
                    for keyword in (
                        "contracts",
                        "FastAPI",
                        "legacy",
                        "runtime",
                        "storage",
                        "workflow",
                        "router",
                    )
                    if keyword.lower() in text.lower()
                ),
            }
        )
    return tests


def _audit_frontend_modules(repo_root: Path) -> list[dict[str, Any]]:
    modules_root = repo_root / FRONTEND_MODULES_ROOT
    modules: list[dict[str, Any]] = []
    if modules_root.exists():
        for module_dir in sorted(path for path in modules_root.iterdir() if path.is_dir()):
            modules.append(
                {
                    "name": module_dir.name,
                    "path": _relative(module_dir, repo_root),
                    "has_index": (module_dir / "index.ts").exists(),
                    "files": sorted(
                        _relative(path, repo_root)
                        for path in module_dir.rglob("*")
                        if path.is_file()
                    ),
                    "has_components_dir": (module_dir / "components").exists(),
                }
            )
    global_frontend_roots = (
        "apps/dashboard/src/lib",
        "apps/dashboard/src/hooks",
        "apps/dashboard/src/components",
        "apps/dashboard/src/features",
    )
    global_counts = {
        root: len([path for path in (repo_root / root).rglob("*") if path.is_file()])
        for root in global_frontend_roots
        if (repo_root / root).exists()
    }
    modules.append(
        {
            "name": "_global_frontend_ownership_snapshot",
            "path": "apps/dashboard/src",
            "has_index": None,
            "files": [],
            "has_components_dir": None,
            "global_file_counts": dict(sorted(global_counts.items())),
            "module_boundary_test": (modules_root / "moduleBoundaries.test.ts").exists(),
        }
    )
    return modules


def _read_frontend_boundary_policy(repo_root: Path) -> dict[str, Any]:
    path = repo_root / FRONTEND_BOUNDARY_POLICY_PATH
    if not path.exists():
        return {
            "schema_version": None,
            "shared_module": "shared",
            "feature_modules": [],
            "allowed_shared_deep_imports": [],
            "allowed_app_deep_module_imports": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _frontend_policy_import_key(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("key") or "")
    return str(entry)


def _frontend_policy_import_details(entries: Any) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    if not isinstance(entries, list):
        return details
    for entry in entries:
        if isinstance(entry, dict):
            details.append({**entry, "key": _frontend_policy_import_key(entry)})
        else:
            key = str(entry)
            details.append(
                {
                    "key": key,
                    "source": key.split(" -> ", 1)[0] if " -> " in key else "",
                    "target": key.split(" -> ", 1)[1] if " -> " in key else "",
                    "owner": "",
                    "rationale": "",
                    "removal_condition": "",
                }
            )
    return sorted(details, key=lambda item: str(item["key"]))


def _frontend_source_files(repo_root: Path) -> list[Path]:
    app_root = repo_root / FRONTEND_APP_ROOT
    if not app_root.exists():
        return []
    return sorted(
        path for path in app_root.rglob("*") if path.is_file() and path.suffix in {".ts", ".tsx"}
    )


def _frontend_import_specifiers(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [
        match.group(1) or match.group(2)
        for match in TS_IMPORT_SPECIFIER_RE.finditer(text)
        if match.group(1) or match.group(2)
    ]


def _frontend_boundary_source_path(path: Path, repo_root: Path) -> str:
    modules_root = repo_root / FRONTEND_MODULES_ROOT
    app_root = repo_root / FRONTEND_APP_ROOT
    try:
        return f"./{path.relative_to(modules_root).as_posix()}"
    except ValueError:
        return f"../{path.relative_to(app_root).as_posix()}"


def _frontend_deep_module_import_key(
    repo_root: Path,
    path: Path,
    import_specifier: str,
    module_names: set[str],
) -> str | None:
    alias_match = re.match(r"^@/modules/([^/]+)/(.+)", import_specifier)
    source_path = _frontend_boundary_source_path(path, repo_root)
    if alias_match:
        return f"{source_path} -> @/modules/{alias_match.group(1)}/{alias_match.group(2)}"

    if not import_specifier.startswith("."):
        return None

    target = (path.parent / import_specifier).resolve()
    modules_root = (repo_root / FRONTEND_MODULES_ROOT).resolve()
    try:
        target_rel = target.relative_to(modules_root).as_posix()
    except ValueError:
        return None
    parts = target_rel.split("/")
    if len(parts) < 2 or parts[0] not in module_names:
        return None
    return f"{source_path} -> @/modules/{parts[0]}/{'/'.join(parts[1:])}"


def _module_name_from_deep_import_key(key: str) -> str | None:
    match = re.search(r" -> @/modules/([^/]+)/", key)
    return match.group(1) if match else None


def _audit_frontend_boundaries(repo_root: Path) -> dict[str, Any]:
    policy = _read_frontend_boundary_policy(repo_root)
    modules_root = repo_root / FRONTEND_MODULES_ROOT
    module_names = _frontend_module_names(modules_root)
    module_name_set = set(module_names)
    shared_module = str(policy.get("shared_module") or "shared")
    feature_modules = [module for module in module_names if module != shared_module]
    expected_feature_modules = sorted(str(item) for item in policy.get("feature_modules", []))
    missing_indexes = [
        module_name
        for module_name in module_names
        if not (modules_root / module_name / "index.ts").exists()
    ]
    allowed_shared_deep_import_details = _frontend_policy_import_details(
        policy.get("allowed_shared_deep_imports", [])
    )
    allowed_app_deep_module_import_details = _frontend_policy_import_details(
        policy.get("allowed_app_deep_module_imports", [])
    )
    allowed_shared_deep_imports = sorted(
        _frontend_policy_import_key(item) for item in policy.get("allowed_shared_deep_imports", [])
    )
    allowed_app_deep_module_imports = sorted(
        _frontend_policy_import_key(item)
        for item in policy.get("allowed_app_deep_module_imports", [])
    )

    deep_imports = _collect_frontend_deep_imports(
        repo_root,
        modules_root=modules_root,
        module_name_set=module_name_set,
        shared_module=shared_module,
        feature_modules=feature_modules,
    )

    unexpected_shared_deep_imports = sorted(
        set(deep_imports["feature_to_shared"]) - set(allowed_shared_deep_imports)
    )
    unexpected_app_deep_module_imports = sorted(
        set(deep_imports["app"]) - set(allowed_app_deep_module_imports)
    )
    return {
        "policy_path": FRONTEND_BOUNDARY_POLICY_PATH.as_posix(),
        "policy_schema_version": policy.get("schema_version"),
        "shared_module": shared_module,
        "expected_feature_modules": expected_feature_modules,
        "feature_modules": feature_modules,
        "missing_indexes": missing_indexes,
        "module_boundary_test": (modules_root / "moduleBoundaries.test.ts").exists(),
        "allowed_shared_deep_imports": allowed_shared_deep_imports,
        "allowed_app_deep_module_imports": allowed_app_deep_module_imports,
        "allowed_shared_deep_import_details": allowed_shared_deep_import_details,
        "allowed_app_deep_module_import_details": allowed_app_deep_module_import_details,
        "feature_to_feature_deep_imports": sorted(set(deep_imports["feature_to_feature"])),
        "feature_to_shared_deep_imports": sorted(set(deep_imports["feature_to_shared"])),
        "shared_to_feature_deep_imports": sorted(set(deep_imports["shared_to_feature"])),
        "app_deep_module_imports": sorted(set(deep_imports["app"])),
        "unexpected_shared_deep_imports": unexpected_shared_deep_imports,
        "unexpected_app_deep_module_imports": unexpected_app_deep_module_imports,
        "deep_import_count": len(
            set(
                [
                    *deep_imports["feature_to_feature"],
                    *deep_imports["feature_to_shared"],
                    *deep_imports["shared_to_feature"],
                    *deep_imports["app"],
                ]
            )
        ),
    }


def _frontend_module_names(modules_root: Path) -> list[str]:
    if not modules_root.exists():
        return []
    return sorted(path.name for path in modules_root.iterdir() if path.is_dir())


def _collect_frontend_deep_imports(
    repo_root: Path,
    *,
    modules_root: Path,
    module_name_set: set[str],
    shared_module: str,
    feature_modules: list[str],
) -> dict[str, list[str]]:
    deep_imports: dict[str, list[str]] = {
        "feature_to_feature": [],
        "feature_to_shared": [],
        "shared_to_feature": [],
        "app": [],
    }
    for path in _frontend_source_files(repo_root):
        source_module = _frontend_source_module(path, modules_root)
        for import_specifier in _frontend_import_specifiers(path):
            key = _frontend_deep_module_import_key(
                repo_root, path, import_specifier, module_name_set
            )
            _append_frontend_deep_import(
                deep_imports,
                key=key,
                source_module=source_module,
                shared_module=shared_module,
                feature_modules=feature_modules,
            )
    return deep_imports


def _frontend_source_module(path: Path, modules_root: Path) -> str | None:
    try:
        return path.relative_to(modules_root).parts[0]
    except ValueError:
        return None


def _append_frontend_deep_import(
    deep_imports: dict[str, list[str]],
    *,
    key: str | None,
    source_module: str | None,
    shared_module: str,
    feature_modules: list[str],
) -> None:
    if key is None:
        return
    if source_module is None:
        deep_imports["app"].append(key)
        return
    target_module = _module_name_from_deep_import_key(key)
    if source_module == shared_module and target_module in feature_modules:
        deep_imports["shared_to_feature"].append(key)
    elif source_module in feature_modules and target_module == shared_module:
        deep_imports["feature_to_shared"].append(key)
    elif (
        source_module in feature_modules
        and target_module in feature_modules
        and target_module != source_module
    ):
        deep_imports["feature_to_feature"].append(key)


def _audit_supporting_surfaces(repo_root: Path) -> dict[str, Any]:
    roots = {
        "backend_scripts": "backend/scripts",
        "backend_tests": "backend/tests",
        "docs": "docs",
        "mex_memory": ".mex",
        "frontend": "apps/dashboard/src",
    }
    return {
        name: {
            "path": path,
            "exists": (repo_root / path).exists(),
            "file_count": len(
                [
                    item
                    for item in (repo_root / path).rglob("*")
                    if item.is_file() and "__pycache__" not in item.parts
                ]
            )
            if (repo_root / path).exists()
            else 0,
        }
        for name, path in roots.items()
    }


def _ownership_entries(repo_root: Path) -> list[dict[str, Any]]:
    return [
        _entry_to_dict(entry, repo_root)
        for entry in sorted(OWNERSHIP_ENTRIES, key=lambda item: item.id)
    ]


def _backend_app_python_files(repo_root: Path) -> list[str]:
    return [
        _relative(path, repo_root)
        for path in _python_files(repo_root / "backend/app")
        if not path.name.endswith(".pyi")
    ]


def _untracked_backend_app_files(repo_root: Path, entries: list[dict[str, Any]]) -> list[str]:
    classified_paths = {
        path
        for entry in entries
        for path in entry["existing_paths"]
        if path.startswith("backend/app/")
    }
    return [path for path in _backend_app_python_files(repo_root) if path not in classified_paths]


def _overlapping_backend_app_files(entries: list[dict[str, Any]]) -> dict[str, list[str]]:
    owners: dict[str, list[str]] = {}
    for entry in entries:
        for path in entry["existing_paths"]:
            if not path.startswith("backend/app/"):
                continue
            owners.setdefault(path, []).append(entry["id"])
    return {
        path: sorted(entry_ids) for path, entry_ids in sorted(owners.items()) if len(entry_ids) > 1
    }


def _residual_boundary_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry for entry in entries if entry["category"] == RESIDUAL_BOUNDARY_CATEGORY]


def _read_residual_boundary_manifest(repo_root: Path) -> dict[str, Any]:
    path = repo_root / RESIDUAL_BOUNDARY_GUARD_PATH
    if not path.exists():
        return {"schema_version": REPORT_SCHEMA_VERSION, "entries": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _residual_boundary_guard(repo_root: Path, entries: list[dict[str, Any]]) -> dict[str, Any]:
    manifest = _read_residual_boundary_manifest(repo_root)
    expected_by_owner = {str(entry.get("owner")): entry for entry in manifest.get("entries", [])}
    residual_entries = _residual_boundary_entries(entries)
    actual_owners = {entry["owner"] for entry in residual_entries}
    expected_owners = set(expected_by_owner)
    violations: list[str] = []
    required_metadata = (
        "owner",
        "entry_id",
        "related_issue",
        "rationale",
        "removal_condition",
        "verification_scope",
        "paths",
        "existing_paths",
        "public_api_fingerprint",
    )

    for missing_owner in sorted(actual_owners - expected_owners):
        violations.append(f"{missing_owner}: missing residual boundary manifest entry")
    for stale_owner in sorted(expected_owners - actual_owners):
        violations.append(f"{stale_owner}: manifest entry has no matching residual boundary")

    guard_entries: list[dict[str, Any]] = []
    for entry in residual_entries:
        owner = entry["owner"]
        expected = expected_by_owner.get(owner, {})
        actual_paths = sorted(entry["existing_paths"])
        actual_fingerprint = _public_api_fingerprint(repo_root, actual_paths)
        expected_paths = sorted(str(path) for path in expected.get("existing_paths", []))
        expected_fingerprint = sorted(
            str(item) for item in expected.get("public_api_fingerprint", [])
        )
        missing_metadata = [key for key in required_metadata if not expected.get(key)]
        if missing_metadata:
            violations.append(f"{owner}: missing manifest metadata {', '.join(missing_metadata)}")
        if expected.get("entry_id") and expected["entry_id"] != entry["id"]:
            violations.append(
                f"{owner}: manifest entry_id {expected['entry_id']} does not match {entry['id']}"
            )
        for path in sorted(set(actual_paths) - set(expected_paths)):
            violations.append(f"{owner}: new residual path {path} is not in manifest")
        for path in sorted(set(expected_paths) - set(actual_paths)):
            violations.append(f"{owner}: manifest path {path} no longer exists")
        for item in sorted(set(actual_fingerprint) - set(expected_fingerprint)):
            violations.append(f"{owner}: new public surface {item} is not in manifest")
        for item in sorted(set(expected_fingerprint) - set(actual_fingerprint)):
            violations.append(f"{owner}: manifest public surface {item} no longer exists")
        guard_entries.append(
            {
                "owner": owner,
                "entry_id": entry["id"],
                "related_issue": expected.get("related_issue"),
                "verification_scope": expected.get("verification_scope"),
                "expected_paths": expected_paths,
                "actual_paths": actual_paths,
                "expected_public_api_fingerprint": expected_fingerprint,
                "actual_public_api_fingerprint": actual_fingerprint,
            }
        )

    return {
        "manifest_path": RESIDUAL_BOUNDARY_GUARD_PATH.as_posix(),
        "boundary_count": len(residual_entries),
        "entries": sorted(guard_entries, key=lambda item: str(item["owner"])),
        "violations": sorted(set(violations)),
    }


def _ensure_report_outputs_exist(repo_root: Path, paths: tuple[Path, ...]) -> None:
    for path in paths:
        output = path if path.is_absolute() else repo_root / path
        output.parent.mkdir(parents=True, exist_ok=True)
        if not output.exists():
            output.write_text("", encoding="utf-8")


def _debt_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    open_entries = [entry for entry in entries if entry["status"] == "open"]
    unmanaged = [
        entry for entry in open_entries if entry["category"] == "unmanaged_feature_surface"
    ]
    residual = [entry for entry in open_entries if entry["category"] == RESIDUAL_BOUNDARY_CATEGORY]
    high_risk = [entry for entry in unmanaged if entry["severity"] == "high"]
    medium_risk = [entry for entry in unmanaged if entry["severity"] == "medium"]
    medium_residual = [entry for entry in residual if entry["severity"] == "medium"]
    return {
        "open_count": len(open_entries),
        "unmanaged_feature_surface_count": len(unmanaged),
        "high_risk_unmanaged_feature_surface_count": len(high_risk),
        "high_risk_unmanaged_feature_surfaces": [entry["id"] for entry in high_risk],
        "medium_unmanaged_feature_surface_count": len(medium_risk),
        "medium_unmanaged_feature_surfaces": [entry["id"] for entry in medium_risk],
        "residual_legacy_feature_boundary_count": len(residual),
        "residual_legacy_feature_boundaries": [entry["id"] for entry in residual],
        "medium_residual_legacy_feature_boundary_count": len(medium_residual),
        "medium_residual_legacy_feature_boundaries": [entry["id"] for entry in medium_residual],
    }


def build_debt_inventory(repo_root: Path, generated_at: str | None = None) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    entries = _ownership_entries(repo_root)
    residual_boundary_guard = _residual_boundary_guard(repo_root, entries)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": generated_at or _utc_timestamp(),
        "scope": {
            "production": "backend/app/**",
            "supporting": [
                "backend/scripts/**",
                "backend/tests/**",
                "docs/**",
                "README.md",
                ".mex/**",
                "apps/dashboard/src/**",
            ],
            "classification_rule": "Every discovered zone is classified as canonical_feature_module, residual_legacy_feature_boundary, unmanaged_feature_surface, shared_platform_infrastructure, compatibility_wrapper, runtime_process_ownership, accepted_architectural_debt, or supporting_tool_test_documentation_frontend_evidence. Residual legacy feature boundaries remain open modularisation debt until migrated, reduced to behavior-free wrappers, or reclassified with proof. Accepted architectural debt entries track documented allowlisted cycles or facade exceptions and stay open until the underlying refactor closes them.",
        },
        "entries": entries,
        "summary": _debt_summary(entries),
        "overlapping_backend_app_python_files": _overlapping_backend_app_files(entries),
        "untracked_backend_app_python_files": _untracked_backend_app_files(repo_root, entries),
        "residual_boundary_guard": residual_boundary_guard,
    }


def _audit_security_checks(repo_root: Path) -> list[dict[str, Any]]:
    workflow_map = {
        "CI": ".github/workflows/ci.yml",
        "Test Quality": ".github/workflows/test-quality.yml",
        "Semgrep": ".github/workflows/semgrep.yml",
        "Secrets Scan": ".github/workflows/secrets.yml",
        "SBOM": ".github/workflows/sbom.yml",
        "Trivy": ".github/workflows/trivy.yml",
        "Complexity": ".github/workflows/complexity.yml",
    }
    checks = [
        {
            "name": name,
            "path": path,
            "exists": (repo_root / path).exists(),
        }
        for name, path in sorted(workflow_map.items())
    ]
    checks.append(
        {
            "name": "CodeQL Default Setup",
            "path": "docs/security/security-baseline.md",
            "exists": "CodeQL Default Setup"
            in _read_text(repo_root, "docs/security/security-baseline.md"),
        }
    )
    checks.append(
        {
            "name": "Gitleaks config",
            "path": ".gitleaks.toml",
            "exists": (repo_root / ".gitleaks.toml").exists(),
        }
    )
    checks.append(
        {
            "name": "Dependabot",
            "path": ".github/dependabot.yml",
            "exists": (repo_root / ".github/dependabot.yml").exists(),
        }
    )
    return sorted(checks, key=lambda check: str(check["name"]))


def _audit_boundaries(repo_root: Path) -> dict[str, Any]:
    contract_files = sorted((repo_root / MODULES_ROOT).glob("*/contracts.py"))
    contract_files.extend(_python_files(repo_root / CONTRACTS_ROOT))
    contract_files.append(repo_root / "backend/app/schemas.py")
    policy_files = _declared_layer_files_for_all_modules(repo_root, "policy")
    repository_files = _declared_layer_files_for_all_modules(repo_root, "repository")
    router_files = _declared_layer_files_for_all_modules(repo_root, "router")

    fastapi_violations: list[str] = []
    for path in _python_files(repo_root / MODULES_ROOT):
        rel = _relative(path, repo_root)
        if path in router_files or rel.endswith("/auth/dependencies.py"):
            continue
        if _has_import_prefix(path, ("fastapi",)):
            fastapi_violations.append(rel)

    return {
        "contracts_forbidden_imports": {
            _relative(path, repo_root): _has_import_prefix(path, FORBIDDEN_CONTRACT_IMPORTS)
            for path in contract_files
            if path.exists()
        },
        "policies_forbidden_imports": {
            _relative(path, repo_root): _has_import_prefix(path, FORBIDDEN_POLICY_IMPORTS)
            for path in policy_files
            if path.exists()
        },
        "repositories_forbidden_imports": {
            _relative(path, repo_root): _has_import_prefix(path, FORBIDDEN_REPOSITORY_IMPORTS)
            for path in repository_files
            if path.exists()
        },
        "routers_importing_models": {
            _relative(path, repo_root): _has_import_prefix(path, ("app.models",))
            for path in router_files
            if path.exists()
        },
        "fastapi_outside_router_or_auth_dependencies": sorted(fastapi_violations),
    }


def _forbidden_runtime_claims(
    workflows: list[dict[str, Any]], queues: list[dict[str, Any]]
) -> dict[str, list[str]]:
    workflow_types = sorted(str(workflow.get("workflow_type")) for workflow in workflows)
    queue_names = sorted(str(queue["name"]) for queue in queues)
    forbidden_workflows = [
        workflow
        for workflow in workflow_types
        if workflow in {"account_editing", "warmup"}
        or "broadcast" in workflow
        or "analytics" in workflow
    ]
    forbidden_queues = [
        queue for queue in queue_names if "broadcast" in queue or "analytics" in queue
    ]
    return {"workflows": forbidden_workflows, "queues": forbidden_queues}


def _backend_overall_status(debt_inventory: dict[str, Any]) -> str:
    if (
        debt_inventory["untracked_backend_app_python_files"]
        or debt_inventory["overlapping_backend_app_python_files"]
        or debt_inventory["residual_boundary_guard"]["violations"]
    ):
        return "RED"
    if debt_inventory["summary"]["high_risk_unmanaged_feature_surface_count"]:
        return "RED"
    if (
        debt_inventory["summary"]["unmanaged_feature_surface_count"]
        or debt_inventory["summary"]["residual_legacy_feature_boundary_count"]
    ):
        return "YELLOW"
    # Backend must not turn GREEN while accepted architectural debt entries
    # (e.g. allowlisted module cycles) stay open. Final closure waits for the
    # underlying refactor that removes those entries.
    accepted_debt_open = any(
        entry["category"] == "accepted_architectural_debt" and entry["status"] == "open"
        for entry in debt_inventory["entries"]
    )
    if accepted_debt_open:
        return "YELLOW"
    return "GREEN"


def _structure_001_finding(
    canonical_modules: list[str],
    summary: dict[str, Any],
    inventory_classification_issues: list[str],
    residual_guard_violations: list[str],
) -> Finding:
    if inventory_classification_issues or residual_guard_violations:
        return Finding(
            id="STRUCTURE-001",
            severity="high",
            status="open",
            area="backend-modules",
            finding="Backend has unclassified, overlapping, or silently expanded production boundaries in backend/app.",
            evidence=(
                f"app.modules.registry imports {', '.join(canonical_modules)}; "
                f"classification issues: {', '.join(inventory_classification_issues) or 'none'}; "
                f"residual guard violations: {', '.join(residual_guard_violations) or 'none'}."
            ),
            risk="High. Architecture audit must not report overall backend GREEN while production files are unclassified, multiply owned, or residual legacy feature boundaries have grown without governance.",
            recommendation="Classify each backend/app production file exactly once and update residual-boundary governance only with related issue, rationale, removal condition, and verification scope.",
            suggested_phase="next",
        )
    if summary["high_risk_unmanaged_feature_surface_count"]:
        return Finding(
            id="STRUCTURE-001",
            severity="high",
            status="open",
            area="backend-modules",
            finding="Backend has canonical modules, but high-risk feature ownership still exists outside app.modules.",
            evidence=(
                f"app.modules.registry imports {', '.join(canonical_modules)}; "
                "high-risk unmanaged feature surfaces: "
                f"{', '.join(summary['high_risk_unmanaged_feature_surfaces'])}."
            ),
            risk="High. Architecture audit must not report overall backend GREEN while high-risk unmanaged domains remain.",
            recommendation="Migrate or explicitly reclassify high-risk unmanaged feature surfaces before claiming backend health.",
            suggested_phase="next",
        )
    if (
        summary["unmanaged_feature_surface_count"]
        or summary["residual_legacy_feature_boundary_count"]
    ):
        return Finding(
            id="STRUCTURE-001",
            severity="medium",
            status="open",
            area="backend-modules",
            finding="Backend has canonical modules plus residual legacy feature boundaries outside app.modules.",
            evidence=(
                f"app.modules.registry imports {', '.join(canonical_modules)}; "
                "medium unmanaged feature surfaces: "
                f"{', '.join(summary['medium_unmanaged_feature_surfaces']) or 'none'}; "
                "residual legacy feature boundaries: "
                f"{', '.join(summary['residual_legacy_feature_boundaries']) or 'none'}."
            ),
            risk="Medium. Residual feature-owned code can continue to bypass canonical module ownership unless it stays visible and guarded.",
            recommendation="Migrate residual legacy feature boundaries through their linked follow-up issues or reduce old paths to behavior-free wrappers before claiming backend GREEN.",
            suggested_phase="Phase 6C+",
        )
    return Finding(
        id="STRUCTURE-001",
        severity="info",
        status="accepted",
        area="backend-modules",
        finding="Backend feature ownership is fully classified under canonical modules or accepted support surfaces.",
        evidence=f"app.modules.registry imports {', '.join(canonical_modules)}; no unmanaged feature debt is open.",
        risk="Low. Keep inventory checks active so new feature-owned code cannot appear unclassified.",
        recommendation="Keep structure audit drift checks required for structural changes.",
        suggested_phase="ongoing",
    )


def _structure_008_finding(
    debt_inventory: dict[str, Any],
    summary: dict[str, Any],
    inventory_classification_issues: list[str],
    residual_guard_violations: list[str],
) -> Finding:
    if inventory_classification_issues or residual_guard_violations:
        return Finding(
            id="STRUCTURE-008",
            severity="high",
            status="open",
            area="unmanaged-backend-surfaces",
            finding="Machine-readable inventory found unclassified, overlapping, or silently expanded backend/app production files.",
            evidence=json.dumps(
                {
                    "untracked_backend_app_python_files": debt_inventory[
                        "untracked_backend_app_python_files"
                    ],
                    "overlapping_backend_app_python_files": debt_inventory[
                        "overlapping_backend_app_python_files"
                    ],
                    "residual_boundary_guard_violations": residual_guard_violations,
                },
                sort_keys=True,
            ),
            risk="High if new feature-owned code can appear outside app.modules without exactly one inventory owner and reviewed residual-boundary governance.",
            recommendation="Keep architecture debt inventory exhaustive and fail checks on untracked, overlapping, or unapproved residual-boundary growth.",
            suggested_phase="next",
        )
    if (
        summary["unmanaged_feature_surface_count"]
        or summary["residual_legacy_feature_boundary_count"]
    ):
        return Finding(
            id="STRUCTURE-008",
            severity="high" if summary["high_risk_unmanaged_feature_surface_count"] else "medium",
            status="open",
            area="unmanaged-backend-surfaces",
            finding="Machine-readable inventory tracks residual backend/app feature surfaces outside canonical modules.",
            evidence=json.dumps(debt_inventory["summary"], sort_keys=True),
            risk="Medium while residual feature boundaries remain outside app.modules; high if guard coverage is weakened.",
            recommendation="Keep residual boundaries open, linked to migration issues, and guarded until migrated or reduced to behavior-free wrappers.",
            suggested_phase="Phase 6C+",
        )
    return Finding(
        id="STRUCTURE-008",
        severity="info",
        status="accepted",
        area="unmanaged-backend-surfaces",
        finding="Machine-readable inventory has no open unmanaged backend/app feature surfaces.",
        evidence=json.dumps(debt_inventory["summary"], sort_keys=True),
        risk="Low while inventory checks keep production files classified.",
        recommendation="Keep architecture debt inventory exhaustive and fail checks on untracked backend/app production files.",
        suggested_phase="ongoing",
    )


def _frontend_boundary_issues(frontend_boundaries: dict[str, Any]) -> list[str]:
    issues = [
        *frontend_boundaries["missing_indexes"],
        *frontend_boundaries["feature_to_feature_deep_imports"],
        *frontend_boundaries["shared_to_feature_deep_imports"],
        *frontend_boundaries["unexpected_shared_deep_imports"],
        *frontend_boundaries["unexpected_app_deep_module_imports"],
    ]
    if not frontend_boundaries["module_boundary_test"]:
        issues.append("module boundary test is missing")
    if frontend_boundaries["feature_modules"] != frontend_boundaries["expected_feature_modules"]:
        issues.append("feature module set differs from policy")
    return issues


def _frontend_boundary_finding(
    frontend_boundaries: dict[str, Any], frontend_boundary_issues: list[str]
) -> Finding:
    return Finding(
        id="STRUCTURE-002",
        severity="high" if frontend_boundary_issues else "info",
        status="open" if frontend_boundary_issues else "accepted",
        area="frontend",
        finding=(
            "Frontend module public-boundary policy has violations."
            if frontend_boundary_issues
            else "Frontend modules expose enforced public indexes and only accepted compatibility deep imports remain."
        ),
        evidence=json.dumps(
            {
                "feature_modules": frontend_boundaries["feature_modules"],
                "shared_module": frontend_boundaries["shared_module"],
                "module_boundary_test": frontend_boundaries["module_boundary_test"],
                "missing_indexes": frontend_boundaries["missing_indexes"],
                "app_deep_module_imports": frontend_boundaries["app_deep_module_imports"],
                "unexpected_app_deep_module_imports": frontend_boundaries[
                    "unexpected_app_deep_module_imports"
                ],
                "unexpected_shared_deep_imports": frontend_boundaries[
                    "unexpected_shared_deep_imports"
                ],
            },
            sort_keys=True,
        ),
        risk=(
            "High. New frontend code can bypass module public APIs if boundary violations are allowed to drift."
            if frontend_boundary_issues
            else "Low. Allowed app compatibility imports are explicit, bounded, and documented with removal conditions."
        ),
        recommendation=(
            "Remove unexpected frontend deep imports or add explicit compatibility-policy debt before merging."
            if frontend_boundary_issues
            else "Keep frontend boundary policy checks required for module or compatibility wrapper changes."
        ),
        suggested_phase="next" if frontend_boundary_issues else "ongoing",
    )


def _findings(
    boundaries: dict[str, Any],
    forbidden_claims: dict[str, list[str]],
    debt_inventory: dict[str, Any],
    frontend_boundaries: dict[str, Any],
) -> list[dict[str, str]]:
    canonical_modules = sorted(
        entry["owner"]
        for entry in debt_inventory["entries"]
        if entry["category"] == "canonical_feature_module"
    )
    summary = debt_inventory["summary"]
    inventory_classification_issues = [
        *debt_inventory["untracked_backend_app_python_files"],
        *debt_inventory["overlapping_backend_app_python_files"].keys(),
    ]
    residual_guard_violations = debt_inventory["residual_boundary_guard"]["violations"]
    structure_001 = _structure_001_finding(
        canonical_modules,
        summary,
        inventory_classification_issues,
        residual_guard_violations,
    )
    structure_008 = _structure_008_finding(
        debt_inventory, summary, inventory_classification_issues, residual_guard_violations
    )
    frontend_boundary_issues = _frontend_boundary_issues(frontend_boundaries)
    frontend_finding = _frontend_boundary_finding(frontend_boundaries, frontend_boundary_issues)

    findings = [
        structure_001,
        frontend_finding,
        Finding(
            id="STRUCTURE-003",
            severity="info",
            status="accepted",
            area="storage-contracts",
            finding="Shared contracts and global DTO/ORM storage boundaries are accepted platform surfaces.",
            evidence="backend/app/contracts exists for low-risk shared DTOs; app.schemas re-exports moved DTOs for compatibility.",
            risk="Low while contracts purity, router ORM, and inventory checks keep shared storage boundaries from attracting unguarded feature ownership.",
            recommendation="Promote DTOs to module contracts only when behavior changes; keep shared-contract and ORM checks required.",
            suggested_phase="ongoing",
        ),
        Finding(
            id="STRUCTURE-004",
            severity="low",
            status="accepted",
            area="legacy-wrappers",
            finding="Legacy API/service/worker wrappers remain import-compatible with a static deprecation plan.",
            evidence="Wrappers include compatibility docstrings and are documented in legacy-wrapper-audit.md, legacy-wrapper-deprecation-plan.md, and legacy-wrappers.json.",
            risk="Low while architecture tests prevent modules from importing legacy wrappers.",
            recommendation="Advance stages only in dedicated compatibility-preserving PRs; do not remove wrappers before Stage 5.",
            suggested_phase="Phase 25",
        ),
        Finding(
            id="STRUCTURE-005",
            severity="info",
            status="accepted",
            area="runtime",
            finding="Reserved queue ownership is logically split into dedicated runtime roles.",
            evidence="Runtime role metadata maps each reserved queue to a dedicated worker role; maintenance_worker maps only to maintenance_jobs.",
            risk="Low. Resource-constrained staging may still group queues in one physical worker by using raw --queues mode without --role.",
            recommendation="Keep logical roles narrow and split physical worker services only when production resources allow it.",
            suggested_phase="Phase 26",
        ),
        Finding(
            id="STRUCTURE-006",
            severity="info",
            status="accepted",
            area="architecture-tests",
            finding="Architecture tests contain duplicated static-analysis helper patterns.",
            evidence="Multiple tests parse imports and source files independently with small local helper functions.",
            risk="Low. Duplication is accepted for small, explicit guard tests while architecture boundaries are stable.",
            recommendation="Consolidate helpers only when a future boundary change makes duplication noisy.",
            suggested_phase="ongoing",
        ),
        Finding(
            id="STRUCTURE-007",
            severity="info",
            status="accepted",
            area="security",
            finding="Security baseline workflows and documentation are present.",
            evidence="CI, Test Quality, Semgrep, Secrets Scan, SBOM, Trivy, Complexity, Gitleaks config, and security docs exist.",
            risk="Low. Branch protection remains a repository setting outside source control.",
            recommendation="Keep security docs in sync with GitHub branch protection and workflow policy changes.",
            suggested_phase="ongoing",
        ),
        structure_008,
    ]
    if any(boundaries["contracts_forbidden_imports"].values()) or any(
        boundaries["routers_importing_models"].values()
    ):
        findings.append(
            Finding(
                id="STRUCTURE-009",
                severity="high",
                status="open",
                area="storage-contracts",
                finding="Static audit found a forbidden ORM import in a contract or router boundary.",
                evidence=json.dumps(
                    {
                        "contracts": boundaries["contracts_forbidden_imports"],
                        "routers": boundaries["routers_importing_models"],
                    },
                    sort_keys=True,
                ),
                risk="High. Public contracts or routers could couple directly to persistence details.",
                recommendation="Fix the boundary violation in a dedicated follow-up PR.",
                suggested_phase="next",
            )
        )
    if forbidden_claims["workflows"] or forbidden_claims["queues"]:
        findings.append(
            Finding(
                id="STRUCTURE-010",
                severity="high",
                status="open",
                area="workflow-runtime",
                finding="Static audit found a forbidden broadcast/analytics or legacy workflow/queue claim.",
                evidence=json.dumps(forbidden_claims, sort_keys=True),
                risk="High. Runtime behavior may have been introduced before module readiness.",
                recommendation="Remove or document the unexpected workflow/queue in a dedicated follow-up PR.",
                suggested_phase="next",
            )
        )
    return [asdict(finding) for finding in sorted(findings, key=lambda finding: finding.id)]


def build_report(repo_root: Path, generated_at: str | None = None) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    generated_at = generated_at or _utc_timestamp()
    modules = _audit_modules(repo_root)
    runtime_roles = _audit_runtime_roles(repo_root)
    queues = _audit_queues(repo_root, runtime_roles)
    workflows = _workflow_specs(repo_root)
    boundaries = _audit_boundaries(repo_root)
    frontend_boundaries = _audit_frontend_boundaries(repo_root)
    forbidden_claims = _forbidden_runtime_claims(workflows, queues)
    debt_inventory = build_debt_inventory(repo_root, generated_at)
    public_facade_exceptions = _read_json(repo_root / PUBLIC_FACADE_EXCEPTIONS_PATH)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "backend_overall_status": _backend_overall_status(debt_inventory),
        "modules": modules,
        "runtime_roles": runtime_roles,
        "queues": queues,
        "legacy_wrappers": _audit_legacy_wrappers(repo_root),
        "shared_contracts": _audit_shared_contracts(repo_root),
        "architecture_tests": _audit_architecture_tests(repo_root),
        "frontend_modules": _audit_frontend_modules(repo_root),
        "frontend_boundaries": frontend_boundaries,
        "supporting_surfaces": _audit_supporting_surfaces(repo_root),
        "security_checks": _audit_security_checks(repo_root),
        "debt_inventory": debt_inventory,
        "public_facade_exceptions": public_facade_exceptions,
        "findings": _findings(boundaries, forbidden_claims, debt_inventory, frontend_boundaries),
        "boundaries": boundaries,
        "workflows": workflows,
        "forbidden_runtime_claims": forbidden_claims,
        "recommended_next_phases": [
            "Ongoing - keep architecture drift checks, wrapper audit, docs audit, and benchmark infrastructure healthy",
            "Ongoing - keep accepted public facade exceptions visible in docs and validated by architecture tests",
            "Ongoing - keep structure audit and boundary checks required for structural changes",
        ],
    }


def render_json_report(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def render_debt_inventory(report: dict[str, Any]) -> str:
    return json.dumps(report["debt_inventory"], indent=2, sort_keys=True) + "\n"


def _markdown_table(headers: tuple[str, ...], rows: list[tuple[Any, ...]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value).replace("\n", " ") for value in row) + " |")
    return "\n".join(lines)


def _status_for_entry(entry: dict[str, Any]) -> str:
    if entry["category"] == "canonical_feature_module":
        return "GREEN"
    if entry["category"] in {"unmanaged_feature_surface", RESIDUAL_BOUNDARY_CATEGORY}:
        return "RED" if entry["severity"] == "high" else "YELLOW"
    if entry["status"] == "open":
        return "YELLOW"
    return "GREEN"


def _backend_overall_evidence(
    debt_summary: dict[str, Any], debt_inventory: dict[str, Any] | None = None
) -> str:
    high_count = debt_summary["high_risk_unmanaged_feature_surface_count"]
    medium_count = debt_summary["medium_unmanaged_feature_surface_count"]
    residual_count = debt_summary["residual_legacy_feature_boundary_count"]
    if high_count or medium_count:
        return (
            f"{high_count} high-risk and {medium_count} medium unmanaged feature surfaces remain."
        )
    if residual_count:
        return f"{residual_count} residual legacy feature boundaries remain outside app.modules."
    accepted_open = (
        [
            entry["id"]
            for entry in (debt_inventory or {}).get("entries", [])
            if entry["category"] == "accepted_architectural_debt" and entry["status"] == "open"
        ]
        if debt_inventory is not None
        else []
    )
    if accepted_open:
        return (
            f"{len(accepted_open)} accepted architectural debt entries remain open: "
            + ", ".join(sorted(accepted_open))
            + "."
        )
    return "No unmanaged or residual feature-boundary debt remains."


def _backend_overall_risk(
    debt_summary: dict[str, Any], debt_inventory: dict[str, Any] | None = None
) -> str:
    if debt_summary["high_risk_unmanaged_feature_surface_count"]:
        return (
            "High-risk unmanaged feature surfaces must not be hidden behind overall backend health."
        )
    if debt_summary["medium_unmanaged_feature_surface_count"]:
        return "Architecture audit must not claim overall GREEN while classified medium or high unmanaged domains remain."
    if debt_summary["residual_legacy_feature_boundary_count"]:
        return "Architecture audit must not claim overall GREEN while residual feature-owned boundaries remain outside canonical modules."
    accepted_open = (
        any(
            entry["category"] == "accepted_architectural_debt" and entry["status"] == "open"
            for entry in (debt_inventory or {}).get("entries", [])
        )
        if debt_inventory is not None
        else False
    )
    if accepted_open:
        return "Architecture audit must not claim overall GREEN while accepted architectural debt entries (e.g. allowlisted module cycles) remain open."
    return "Low while structure audit checks keep feature ownership classified."


def _backend_overall_followup(
    debt_summary: dict[str, Any], debt_inventory: dict[str, Any] | None = None
) -> str:
    if debt_summary["high_risk_unmanaged_feature_surface_count"]:
        return "Migrate or explicitly reclassify high-risk unmanaged feature surfaces."
    if debt_summary["medium_unmanaged_feature_surface_count"]:
        return "Keep medium debt visible while Phase 5/6 continue."
    if debt_summary["residual_legacy_feature_boundary_count"]:
        return (
            "Migrate linked residual boundaries or reduce legacy paths to behavior-free wrappers."
        )
    accepted_open = (
        any(
            entry["category"] == "accepted_architectural_debt" and entry["status"] == "open"
            for entry in (debt_inventory or {}).get("entries", [])
        )
        if debt_inventory is not None
        else False
    )
    if accepted_open:
        return "Close documented accepted architectural debt entries (extract shared primitives, drop cycle exceptions)."
    return "Keep drift checks required for structural changes."


def _backend_modules_status(residual_debt: list[dict[str, Any]]) -> str:
    return "YELLOW" if residual_debt else "GREEN"


def _backend_modules_risk(residual_debt: list[dict[str, Any]]) -> str:
    if residual_debt:
        return "Canonical ownership exists for migrated modules only; residual feature behavior still lives outside app.modules."
    return "Low while registered modules and support surfaces remain classified."


def _backend_modules_followup(residual_debt: list[dict[str, Any]]) -> str:
    if residual_debt:
        return "Use linked residual-boundary follow-ups before restoring GREEN status."
    return "Keep module registry and inventory checks in sync."


def _unmanaged_debt_risk(unmanaged_debt: list[dict[str, Any]]) -> str:
    if unmanaged_debt:
        return "New feature behavior can bypass app.modules unless classified and guarded."
    return "Low while new backend/app production files fail when unclassified."


def _unmanaged_debt_followup(unmanaged_debt: list[dict[str, Any]]) -> str:
    if unmanaged_debt:
        return "Keep debt inventory exhaustive and CI-enforced."
    return "Keep untracked backend/app file checks active."


def render_markdown_report(report: dict[str, Any]) -> str:
    context = _markdown_report_context(report)
    lines = [
        "# Structure Audit",
        "",
        f"Generated snapshot: `{report['generated_at']}`",
        "",
        "This generated audit records the current compatibility-first modular monolith boundaries, the canonical module registry, runtime ownership, and tracked migration debt. The machine-readable companion reports are `docs/architecture/structure-audit.json` and `docs/architecture/architecture-debt-inventory.json`, both generated by `backend/scripts/structure_audit.py`.",
        "",
        "Status legend:",
        "",
        "- `GREEN`: structurally healthy and enforced by tests or static checks.",
        "- `YELLOW`: transitional but acceptable with documented constraints.",
        "- `RED`: structural risk or contradictory boundary that needs immediate follow-up.",
        "",
        *_markdown_executive_summary_section(report, context),
        *_markdown_backend_registry_section(context),
        *_markdown_ownership_inventory_section(context),
        *_markdown_required_domains_section(context),
        *_markdown_runtime_section(context),
        *_markdown_guard_status_section(report, context),
        *_markdown_frontend_policy_section(context),
        *_markdown_risk_register_section(context),
        *_markdown_facade_exceptions_section(report),
        *_markdown_next_phases_section(report),
    ]
    return "\n".join(lines)


def _markdown_report_context(report: dict[str, Any]) -> dict[str, Any]:
    debt_inventory = report["debt_inventory"]
    debt_entries = debt_inventory["entries"]
    frontend_boundaries = report["frontend_boundaries"]
    high_debt = _debt_entries(debt_entries, category="unmanaged_feature_surface", severity="high")
    unmanaged_debt = _debt_entries(debt_entries, category="unmanaged_feature_surface")
    residual_debt = _debt_entries(debt_entries, category=RESIDUAL_BOUNDARY_CATEGORY)
    return {
        "debt_inventory": debt_inventory,
        "debt_entries": debt_entries,
        "debt_summary": debt_inventory["summary"],
        "modules": report["modules"],
        "runtime_roles": report["runtime_roles"],
        "findings": report["findings"],
        "frontend_boundaries": frontend_boundaries,
        "frontend_boundary_issues": _frontend_boundary_issues(frontend_boundaries),
        "high_debt": high_debt,
        "unmanaged_debt": unmanaged_debt,
        "residual_debt": residual_debt,
        "residual_guard_violations": debt_inventory["residual_boundary_guard"]["violations"],
    }


def _debt_entries(
    entries: list[dict[str, Any]], *, category: str, severity: str | None = None
) -> list[dict[str, Any]]:
    return [
        entry
        for entry in entries
        if entry["category"] == category and (severity is None or entry["severity"] == severity)
    ]


def _markdown_executive_summary_section(
    report: dict[str, Any], context: dict[str, Any]
) -> list[str]:
    return [
        "## 1. Executive Summary",
        "",
        _markdown_table(
            ("Area", "Status", "Evidence", "Risk", "Recommended follow-up"),
            _markdown_executive_summary_rows(report, context),
        ),
        "",
    ]


def _markdown_executive_summary_rows(
    report: dict[str, Any], context: dict[str, Any]
) -> list[tuple[str, str, str, str, str]]:
    debt_summary = context["debt_summary"]
    debt_inventory = context["debt_inventory"]
    return [
        (
            "Backend overall",
            report["backend_overall_status"],
            _backend_overall_evidence(debt_summary, debt_inventory),
            _backend_overall_risk(debt_summary, debt_inventory),
            _backend_overall_followup(debt_summary, debt_inventory),
        ),
        _backend_modules_summary_row(context),
        _unmanaged_feature_summary_row(context),
        _residual_feature_summary_row(context),
        _residual_guard_summary_row(context),
        (
            "Generated artifacts",
            "GREEN",
            "JSON, Markdown, and debt inventory render from one report pipeline.",
            "Low while drift tests compare committed artifacts to deterministic renderers.",
            "Run `python backend/scripts/structure_audit.py --check` after structural changes.",
        ),
        _frontend_ownership_summary_row(context),
    ]


def _backend_modules_summary_row(context: dict[str, Any]) -> tuple[str, str, str, str, str]:
    debt = [*context["unmanaged_debt"], *context["residual_debt"]]
    modules = context["modules"]
    return (
        "Backend modules",
        _backend_modules_status(debt),
        "Registered modules: "
        + ", ".join(module["name"] for module in modules if module["registered"]),
        _backend_modules_risk(debt),
        _backend_modules_followup(debt),
    )


def _unmanaged_feature_summary_row(context: dict[str, Any]) -> tuple[str, str, str, str, str]:
    high_debt = context["high_debt"]
    unmanaged_debt = context["unmanaged_debt"]
    status = "RED" if high_debt else "YELLOW" if unmanaged_debt else "GREEN"
    evidence = (
        ", ".join(entry["owner"] for entry in high_debt)
        if high_debt
        else ", ".join(entry["owner"] for entry in unmanaged_debt)
        or "No untracked unmanaged feature surfaces; residual debt is reported separately."
    )
    return (
        "Unmanaged feature debt",
        status,
        evidence,
        _unmanaged_debt_risk(unmanaged_debt),
        _unmanaged_debt_followup(unmanaged_debt),
    )


def _residual_feature_summary_row(context: dict[str, Any]) -> tuple[str, str, str, str, str]:
    residual_debt = context["residual_debt"]
    return (
        "Residual legacy feature boundaries",
        "YELLOW" if residual_debt else "GREEN",
        ", ".join(entry["owner"] for entry in residual_debt)
        or "No residual legacy feature boundaries.",
        _residual_feature_risk(residual_debt),
        _residual_feature_followup(residual_debt),
    )


def _residual_feature_risk(residual_debt: list[dict[str, Any]]) -> str:
    if residual_debt:
        return "Feature behavior remains outside canonical modules and must stay visible."
    return "Low while no residual feature behavior remains outside canonical modules."


def _residual_feature_followup(residual_debt: list[dict[str, Any]]) -> str:
    if residual_debt:
        return "Migrate through linked follow-up issues or reduce legacy paths to wrappers."
    return "Keep residual-boundary guard active."


def _residual_guard_summary_row(context: dict[str, Any]) -> tuple[str, str, str, str, str]:
    violations = context["residual_guard_violations"]
    return (
        "Residual boundary non-growth guard",
        "RED" if violations else "GREEN",
        "<br>".join(violations) or _residual_guard_clean_evidence(),
        _residual_guard_risk(violations),
        _residual_guard_followup(violations),
    )


def _residual_guard_clean_evidence() -> str:
    return (
        "Public-surface/non-growth guard covers current residual files, "
        "paths, and public route/function/class fingerprints."
    )


def _residual_guard_risk(violations: list[str]) -> str:
    if violations:
        return "Residual feature boundaries can grow silently if the manifest is stale."
    return (
        "Low for public-surface growth only; behavior changes inside existing residual files "
        "still require migration or an approved architecture exception."
    )


def _residual_guard_followup(violations: list[str]) -> str:
    if violations:
        return "Update the manifest only with a linked issue, rationale, and removal condition."
    return (
        "Use migration issues for behavior changes; a manifest update alone "
        "does not replace canonical migration."
    )


def _frontend_ownership_summary_row(context: dict[str, Any]) -> tuple[str, str, str, str, str]:
    frontend_boundaries = context["frontend_boundaries"]
    issues = context["frontend_boundary_issues"]
    return (
        "Frontend ownership",
        "RED" if issues else "GREEN",
        "Feature modules: "
        + ", ".join(frontend_boundaries["feature_modules"])
        + "; accepted app compatibility deep imports: "
        + str(len(frontend_boundaries["app_deep_module_imports"]))
        + ".",
        _frontend_ownership_risk(issues),
        _frontend_ownership_followup(issues),
    )


def _frontend_ownership_risk(issues: list[str]) -> str:
    if issues:
        return "Frontend module boundary violations are present."
    return "Frontend public APIs are enforced; compatibility imports are explicit and bounded."


def _frontend_ownership_followup(issues: list[str]) -> str:
    if issues:
        return "Remove unexpected deep imports or record them in the frontend boundary policy."
    return "Keep frontend boundary policy checks required for module or wrapper changes."


def _markdown_backend_registry_section(context: dict[str, Any]) -> list[str]:
    return [
        "## 2. Backend Module Registry",
        "",
        _markdown_table(
            ("Module", "Registered", "Router", "Workflows", "Status"),
            [_backend_registry_row(module) for module in context["modules"]],
        ),
        "",
    ]


def _backend_registry_row(module: dict[str, Any]) -> tuple[str, Any, str, str, str]:
    workflows = ", ".join(str(workflow.get("workflow_type")) for workflow in module["workflows"])
    return (
        module["name"],
        module["registered"],
        module["router_path"] or "none",
        workflows or "none",
        "GREEN" if module["registered"] or module["documentation_only"] else "YELLOW",
    )


def _markdown_ownership_inventory_section(context: dict[str, Any]) -> list[str]:
    return [
        "## 3. Ownership Inventory",
        "",
        _markdown_table(
            ("ID", "Category", "Status", "Severity", "Owner", "Target owner", "Phase"),
            [
                (
                    entry["id"],
                    entry["category"],
                    _status_for_entry(entry),
                    entry["severity"],
                    entry["owner"],
                    entry["target_owner"],
                    entry["phase"],
                )
                for entry in context["debt_entries"]
            ],
        ),
        "",
    ]


def _markdown_required_domains_section(context: dict[str, Any]) -> list[str]:
    return [
        "## 4. Required Unmanaged And Residual Domains",
        "",
        _markdown_table(
            (
                "Domain",
                "Category",
                "Severity",
                "Current paths",
                "Target owner",
                "Removal condition",
            ),
            [
                _required_domain_row(entry)
                for entry in context["debt_entries"]
                if _is_required_domain(entry)
            ],
        ),
        "",
    ]


def _is_required_domain(entry: dict[str, Any]) -> bool:
    return entry["category"] in {"unmanaged_feature_surface", RESIDUAL_BOUNDARY_CATEGORY}


def _required_domain_row(entry: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        entry["owner"],
        entry["category"],
        entry["severity"],
        "<br>".join(entry["paths"]),
        entry["target_owner"],
        entry["removal_condition"],
    )


def _markdown_runtime_section(context: dict[str, Any]) -> list[str]:
    return [
        "## 5. Runtime / Process Structure",
        "",
        _markdown_table(
            ("Role", "Queues", "Live TDLib", "Notes"),
            [_runtime_role_row(role) for role in context["runtime_roles"]],
        ),
        "",
    ]


def _runtime_role_row(role: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        role["name"],
        ", ".join(role.get("queues") or []) or "none",
        "Yes" if role.get("allows_live_tdlib") else "No",
        role.get("description") or "",
    )


def _markdown_guard_status_section(report: dict[str, Any], context: dict[str, Any]) -> list[str]:
    return [
        "## 6. Architecture Guard Status",
        "",
        _markdown_table(("Guard", "Status", "Evidence"), _guard_status_rows(report, context)),
        "",
    ]


def _guard_status_rows(
    report: dict[str, Any], context: dict[str, Any]
) -> list[tuple[str, str, str]]:
    return [
        _untracked_backend_guard_row(report),
        _residual_boundary_guard_row(context),
        _forbidden_contract_imports_row(report),
        _routers_importing_models_row(report),
        _forbidden_runtime_claims_row(report),
    ]


def _untracked_backend_guard_row(report: dict[str, Any]) -> tuple[str, str, str]:
    inventory = report["debt_inventory"]
    issues = [
        *inventory["untracked_backend_app_python_files"],
        *inventory["overlapping_backend_app_python_files"].keys(),
    ]
    return (
        "Untracked backend/app production files",
        "GREEN" if not issues else "RED",
        ", ".join(issues)
        or "All backend/app Python files are classified exactly once by the inventory.",
    )


def _residual_boundary_guard_row(context: dict[str, Any]) -> tuple[str, str, str]:
    violations = context["residual_guard_violations"]
    evidence = (
        "<br>".join(violations)
        or "Public-surface/non-growth guard covers every current residual file and public route/function/class surface; behavior-changing updates still require migration or an approved architecture exception."
    )
    return "Residual boundary growth", "GREEN" if not violations else "RED", evidence


def _forbidden_contract_imports_row(report: dict[str, Any]) -> tuple[str, str, str]:
    imports = report["boundaries"]["contracts_forbidden_imports"]
    return (
        "Forbidden contract imports",
        "GREEN" if not any(imports.values()) else "RED",
        json.dumps(imports, sort_keys=True),
    )


def _routers_importing_models_row(report: dict[str, Any]) -> tuple[str, str, str]:
    imports = report["boundaries"]["routers_importing_models"]
    return (
        "Routers importing ORM models",
        "GREEN" if not any(imports.values()) else "RED",
        json.dumps(imports, sort_keys=True),
    )


def _forbidden_runtime_claims_row(report: dict[str, Any]) -> tuple[str, str, str]:
    claims = report["forbidden_runtime_claims"]
    return (
        "Forbidden runtime claims",
        "GREEN" if claims == {"queues": [], "workflows": []} else "RED",
        json.dumps(claims, sort_keys=True),
    )


def _markdown_frontend_policy_section(context: dict[str, Any]) -> list[str]:
    return [
        "## 7. Frontend Boundary Policy",
        "",
        _markdown_table(("Check", "Status", "Evidence"), _frontend_policy_rows(context)),
        "",
    ]


def _frontend_policy_rows(context: dict[str, Any]) -> list[tuple[str, str, str]]:
    frontend_boundaries = context["frontend_boundaries"]
    return [
        (
            "Public module indexes",
            "GREEN" if not frontend_boundaries["missing_indexes"] else "RED",
            ", ".join(frontend_boundaries["missing_indexes"]) or "Every module has index.ts.",
        ),
        (
            "Feature module set",
            _feature_module_set_status(frontend_boundaries),
            ", ".join(frontend_boundaries["feature_modules"]),
        ),
        (
            "Feature to feature deep imports",
            "GREEN" if not frontend_boundaries["feature_to_feature_deep_imports"] else "RED",
            "<br>".join(frontend_boundaries["feature_to_feature_deep_imports"]) or "None.",
        ),
        (
            "Feature to shared deep imports",
            "GREEN" if not frontend_boundaries["unexpected_shared_deep_imports"] else "RED",
            "<br>".join(frontend_boundaries["feature_to_shared_deep_imports"]) or "None.",
        ),
        (
            "App compatibility deep imports",
            "RED" if frontend_boundaries["unexpected_app_deep_module_imports"] else "GREEN",
            "<br>".join(frontend_boundaries["app_deep_module_imports"]) or "None.",
        ),
    ]


def _feature_module_set_status(frontend_boundaries: dict[str, Any]) -> str:
    if frontend_boundaries["feature_modules"] == frontend_boundaries["expected_feature_modules"]:
        return "GREEN"
    return "RED"


def _markdown_risk_register_section(context: dict[str, Any]) -> list[str]:
    return [
        "## 8. Risk Register",
        "",
        _markdown_table(
            ("ID", "Severity", "Status", "Area", "Finding", "Risk", "Recommendation"),
            [
                (
                    finding["id"],
                    finding["severity"],
                    finding["status"],
                    finding["area"],
                    finding["finding"],
                    finding["risk"],
                    finding["recommendation"],
                )
                for finding in context["findings"]
            ],
        ),
        "",
    ]


def _markdown_facade_exceptions_section(report: dict[str, Any]) -> list[str]:
    return [
        "## 9. Accepted Public Facade Exceptions",
        "",
        (
            "`docs/architecture/public-facade-exceptions.json` lists every accepted "
            "cross-module public facade exception with owner, rationale, and removal condition. "
            "The architecture test `test_public_facade_exceptions_doc_matches_allowlist` "
            "keeps this documentation synchronized with the import allowlist."
        ),
        "",
        _markdown_table(
            ("Owner", "Accepted exceptions"),
            sorted(
                (
                    owner,
                    sum(
                        1
                        for record in report["public_facade_exceptions"]["exceptions"]
                        if record["owner"] == owner
                    ),
                )
                for owner in {
                    record["owner"] for record in report["public_facade_exceptions"]["exceptions"]
                }
            ),
        ),
        "",
    ]


def _markdown_next_phases_section(report: dict[str, Any]) -> list[str]:
    return [
        "## 10. Recommended Next Implementation Issues",
        "",
        _markdown_table(
            ("Phase", "Scope"),
            [
                (phase.split(" - ", 1)[0], phase.split(" - ", 1)[1])
                for phase in report["recommended_next_phases"]
            ],
        ),
        "",
    ]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)


def detect_report_drift(
    repo_root: Path,
    json_path: Path | None = None,
    markdown_path: Path | None = None,
    debt_path: Path | None = None,
) -> list[str]:
    repo_root = repo_root.resolve()
    json_path = json_path or repo_root / DEFAULT_JSON_OUTPUT
    markdown_path = markdown_path or repo_root / DEFAULT_MARKDOWN_OUTPUT
    debt_path = debt_path or repo_root / DEFAULT_DEBT_OUTPUT
    committed_report = _read_json(json_path)
    expected_report = build_report(repo_root, generated_at=str(committed_report["generated_at"]))
    drift: list[str] = []
    if json_path.read_text(encoding="utf-8") != render_json_report(expected_report):
        drift.append(_display_path(json_path, repo_root))
    if markdown_path.read_text(encoding="utf-8") != render_markdown_report(expected_report):
        drift.append(_display_path(markdown_path, repo_root))
    if debt_path.read_text(encoding="utf-8") != render_debt_inventory(expected_report):
        drift.append(_display_path(debt_path, repo_root))
    return drift


def write_report_artifacts(
    repo_root: Path,
    json_path: Path,
    markdown_path: Path,
    debt_path: Path,
    generated_at: str | None = None,
) -> None:
    _ensure_report_outputs_exist(repo_root, (json_path, markdown_path, debt_path))
    report = build_report(repo_root, generated_at=generated_at)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    debt_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(render_json_report(report), encoding="utf-8")
    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    debt_path.write_text(render_debt_inventory(report), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the static project structure audit report.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path. Defaults to docs/architecture/structure-audit.json.",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help="Output Markdown path. Defaults to docs/architecture/STRUCTURE_AUDIT.md.",
    )
    parser.add_argument(
        "--debt-output",
        type=Path,
        default=None,
        help="Output debt inventory path. Defaults to docs/architecture/architecture-debt-inventory.json.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check committed JSON, Markdown, and debt inventory artifacts for drift.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    output = args.output or repo_root / DEFAULT_JSON_OUTPUT
    markdown_output = args.markdown_output or repo_root / DEFAULT_MARKDOWN_OUTPUT
    debt_output = args.debt_output or repo_root / DEFAULT_DEBT_OUTPUT
    if not output.is_absolute():
        output = repo_root / output
    if not markdown_output.is_absolute():
        markdown_output = repo_root / markdown_output
    if not debt_output.is_absolute():
        debt_output = repo_root / debt_output
    if args.check:
        drift = detect_report_drift(repo_root, output, markdown_output, debt_output)
        if drift:
            raise SystemExit(
                "Structure audit artifacts are stale; regenerate them with "
                "`python backend/scripts/structure_audit.py`: " + ", ".join(drift)
            )
        return
    write_report_artifacts(repo_root, output, markdown_output, debt_output)


if __name__ == "__main__":
    main()
