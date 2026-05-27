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
        id="accepted-legacy-account-audit",
        category="accepted_legacy_feature_boundary",
        severity="medium",
        status="accepted",
        owner="account_audit",
        paths=("backend/app/api/account_audit_routes.py",),
        target_owner="accepted legacy account audit boundary",
        phase="Phase 6B",
        removal_condition="Promote to app.modules.account_audit only when account audit behavior changes; keep classified and guarded meanwhile.",
        rationale="Account audit transport is a stable read-only legacy feature boundary backed by shared audit services; Phase 6B accepts it explicitly instead of treating it as hidden account-platform debt.",
    ),
    OwnershipEntry(
        id="accepted-legacy-account-core",
        category="accepted_legacy_feature_boundary",
        severity="medium",
        status="accepted",
        owner="account_core",
        paths=(
            "backend/app/api/account_compat_routes.py",
            "backend/app/api/account_context.py",
            "backend/app/api/accounts.py",
            "backend/app/services/account_bundle.py",
            "backend/app/services/account_capabilities.py",
            "backend/app/services/accounts.py",
            "backend/app/contracts/accounts.py",
            "backend/app/contracts/cross_module_load.py",
        ),
        target_owner="accepted legacy account core boundary",
        phase="Phase 6B",
        removal_condition="Promote to app.modules.account_core only with a dedicated behavior-preserving account-core migration; keep classified and guarded meanwhile.",
        rationale="Core account CRUD, context, bundle, capabilities, and DTO surfaces are stable platform-level account primitives used across modules; Phase 6B accepts the existing boundary explicitly.",
    ),
    OwnershipEntry(
        id="accepted-legacy-account-ggr",
        category="accepted_legacy_feature_boundary",
        severity="medium",
        status="accepted",
        owner="account_ggr",
        paths=(
            "backend/app/api/account_ggr_routes.py",
            "backend/app/services/fraud_score.py",
            "backend/app/services/ggr_calculator.py",
            "backend/app/contracts/ggr.py",
        ),
        target_owner="accepted legacy account GGR/risk scoring boundary",
        phase="Phase 6B",
        removal_condition="Promote to app.modules.account_ggr only when GGR behavior changes; keep classified and guarded meanwhile.",
        rationale="GGR and fraud scoring are stable account risk-scoring surfaces with existing tests and metrics; Phase 6B accepts the legacy boundary explicitly.",
    ),
    OwnershipEntry(
        id="accepted-legacy-account-imports",
        category="accepted_legacy_feature_boundary",
        severity="medium",
        status="accepted",
        owner="account_imports",
        paths=(
            "backend/app/api/account_imports.py",
            "backend/app/services/account_imports.py",
        ),
        target_owner="accepted legacy account imports boundary",
        phase="Phase 6B",
        removal_condition="Promote to app.modules.account_imports only when import behavior changes; keep classified and guarded meanwhile.",
        rationale="Account import is a stable onboarding/import surface; Phase 6B accepts its legacy route/service boundary explicitly.",
    ),
    OwnershipEntry(
        id="accepted-legacy-account-jobs",
        category="accepted_legacy_feature_boundary",
        severity="medium",
        status="accepted",
        owner="account_jobs",
        paths=("backend/app/api/account_jobs_routes.py",),
        target_owner="accepted legacy account jobs boundary",
        phase="Phase 6B",
        removal_condition="Promote to app.modules.account_jobs only when account job transport behavior changes; keep classified and guarded meanwhile.",
        rationale="Account job transport is a stable account workspace/read model boundary over shared job infrastructure; Phase 6B accepts it explicitly.",
    ),
    OwnershipEntry(
        id="accepted-legacy-account-profile-state",
        category="accepted_legacy_feature_boundary",
        severity="medium",
        status="accepted",
        owner="account_profile_state",
        paths=(
            "backend/app/services/profile_audio_state.py",
            "backend/app/services/profile_photo_state.py",
            "backend/app/services/profile_sync.py",
        ),
        target_owner="accepted legacy account profile-state boundary",
        phase="Phase 6B",
        removal_condition="Promote to app.modules.account_editing or a profile-state module only when profile-state behavior changes; keep classified and guarded meanwhile.",
        rationale="Profile audio/photo/sync helpers are stable profile-state support surfaces shared by account editing and runtime sync; Phase 6B accepts the legacy boundary explicitly.",
    ),
    OwnershipEntry(
        id="accepted-legacy-account-proxy",
        category="accepted_legacy_feature_boundary",
        severity="medium",
        status="accepted",
        owner="account_proxy",
        paths=(
            "backend/app/api/account_proxy_routes.py",
            "backend/app/services/proxy_accounts.py",
            "backend/app/services/proxy_checks.py",
        ),
        target_owner="accepted legacy account proxy boundary",
        phase="Phase 6B",
        removal_condition="Promote to app.modules.account_proxy only when proxy assignment/checking behavior changes; keep classified and guarded meanwhile.",
        rationale="Proxy assignment and check surfaces are stable account infrastructure behavior with external-network guards; Phase 6B accepts the legacy boundary explicitly.",
    ),
    OwnershipEntry(
        id="accepted-legacy-account-quarantine",
        category="accepted_legacy_feature_boundary",
        severity="medium",
        status="accepted",
        owner="account_quarantine",
        paths=(
            "backend/app/api/account_quarantine_routes.py",
            "backend/app/services/account_quarantine.py",
            "backend/app/contracts/quarantine.py",
        ),
        target_owner="accepted legacy account quarantine boundary",
        phase="Phase 6B",
        removal_condition="Promote to app.modules.account_quarantine or account_safety only when quarantine behavior changes; keep classified and guarded meanwhile.",
        rationale="Quarantine is stable safety-adjacent account state with route/service/contract coverage; Phase 6B accepts the legacy boundary explicitly.",
    ),
    OwnershipEntry(
        id="accepted-legacy-account-runtime-status",
        category="accepted_legacy_feature_boundary",
        severity="medium",
        status="accepted",
        owner="account_runtime_status",
        paths=(
            "backend/app/api/account_runtime_routes.py",
            "backend/app/api/account_status_routes.py",
            "backend/app/services/account_cooldowns.py",
            "backend/app/services/account_health.py",
            "backend/app/services/account_risk.py",
            "backend/app/services/account_status_monitor.py",
            "backend/app/services/account_terminal_status.py",
            "backend/app/contracts/account_status.py",
        ),
        target_owner="accepted legacy account runtime/status boundary",
        phase="Phase 6B",
        removal_condition="Promote to app.modules.account_runtime_status only when runtime/status behavior changes; keep classified and guarded meanwhile.",
        rationale="Runtime health, status, cooldown, risk, and terminal-state surfaces are stable account runtime read models; Phase 6B accepts the legacy boundary explicitly.",
    ),
    OwnershipEntry(
        id="accepted-legacy-account-validity",
        category="accepted_legacy_feature_boundary",
        severity="medium",
        status="accepted",
        owner="account_validity",
        paths=("backend/app/services/account_validity.py",),
        target_owner="accepted legacy account validity boundary",
        phase="Phase 6B",
        removal_condition="Promote to app.modules.account_validity or account_safety only when validity behavior changes; keep classified and guarded meanwhile.",
        rationale="Validity checks are stable safety-adjacent runtime checks with TDLib/live gates; Phase 6B accepts the legacy boundary explicitly.",
    ),
    OwnershipEntry(
        id="accepted-legacy-story-surfaces",
        category="accepted_legacy_feature_boundary",
        severity="medium",
        status="accepted",
        owner="story",
        paths=(
            "backend/app/api/story_*.py",
            "backend/app/services/story_*.py",
        ),
        target_owner="accepted legacy story boundary",
        phase="Phase 6B",
        removal_condition="Promote to app.modules.story only when story behavior changes; keep classified and guarded meanwhile.",
        rationale="Story draft/post/capability surfaces are stable legacy feature boundaries with live-operation gates; Phase 6B accepts them explicitly.",
    ),
    OwnershipEntry(
        id="accepted-legacy-bought-onboarding",
        category="accepted_legacy_feature_boundary",
        severity="medium",
        status="accepted",
        owner="bought_onboarding",
        paths=(
            "backend/app/api/bought_onboarding_routes.py",
            "backend/app/services/bought_account_onboarding.py",
            "backend/app/contracts/bought_onboarding.py",
        ),
        target_owner="accepted legacy bought-account onboarding boundary",
        phase="Phase 6B",
        removal_condition="Promote to app.modules.bought_onboarding only when bought-account onboarding behavior changes; keep classified and guarded meanwhile.",
        rationale="Bought-account onboarding is a stable account onboarding workflow; Phase 6B accepts the legacy route/service/contract boundary explicitly.",
    ),
    OwnershipEntry(
        id="accepted-legacy-human-behavior",
        category="accepted_legacy_feature_boundary",
        severity="medium",
        status="accepted",
        owner="human_behavior",
        paths=(
            "backend/app/api/human_behavior_routes.py",
            "backend/app/services/human_behavior/**",
            "backend/app/contracts/human_behavior.py",
        ),
        target_owner="accepted legacy human-behavior boundary",
        phase="Phase 6B",
        removal_condition="Promote to app.modules.human_behavior only when human-behavior policy/runtime behavior changes; keep classified and guarded meanwhile.",
        rationale="Human-behavior policy/runtime surfaces are stable feature logic with safety/runtime constraints; Phase 6B accepts the legacy boundary explicitly.",
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
            "backend/app/contracts/notifications.py",
            "backend/app/contracts/queues.py",
            "backend/app/contracts/types.py",
            "backend/app/models.py",
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
        path for path in modules_root.iterdir() if path.is_dir() and path.name != "__pycache__"
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
                "tests_present": (repo_root / "backend/tests/modules" / module_name).exists(),
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
    module_names = (
        sorted(path.name for path in modules_root.iterdir() if path.is_dir())
        if modules_root.exists()
        else []
    )
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

    feature_to_feature_deep_imports: list[str] = []
    feature_to_shared_deep_imports: list[str] = []
    shared_to_feature_deep_imports: list[str] = []
    app_deep_module_imports: list[str] = []

    for path in _frontend_source_files(repo_root):
        try:
            source_module = path.relative_to(modules_root).parts[0]
            inside_modules = True
        except ValueError:
            source_module = None
            inside_modules = False

        for import_specifier in _frontend_import_specifiers(path):
            key = _frontend_deep_module_import_key(
                repo_root, path, import_specifier, module_name_set
            )
            if key is None:
                continue
            target_module = _module_name_from_deep_import_key(key)
            if inside_modules:
                if source_module == shared_module and target_module in feature_modules:
                    shared_to_feature_deep_imports.append(key)
                elif source_module in feature_modules and target_module == shared_module:
                    feature_to_shared_deep_imports.append(key)
                elif (
                    source_module in feature_modules
                    and target_module in feature_modules
                    and target_module != source_module
                ):
                    feature_to_feature_deep_imports.append(key)
            else:
                app_deep_module_imports.append(key)

    unexpected_shared_deep_imports = sorted(
        set(feature_to_shared_deep_imports) - set(allowed_shared_deep_imports)
    )
    unexpected_app_deep_module_imports = sorted(
        set(app_deep_module_imports) - set(allowed_app_deep_module_imports)
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
        "feature_to_feature_deep_imports": sorted(set(feature_to_feature_deep_imports)),
        "feature_to_shared_deep_imports": sorted(set(feature_to_shared_deep_imports)),
        "shared_to_feature_deep_imports": sorted(set(shared_to_feature_deep_imports)),
        "app_deep_module_imports": sorted(set(app_deep_module_imports)),
        "unexpected_shared_deep_imports": unexpected_shared_deep_imports,
        "unexpected_app_deep_module_imports": unexpected_app_deep_module_imports,
        "deep_import_count": len(
            set(
                [
                    *feature_to_feature_deep_imports,
                    *feature_to_shared_deep_imports,
                    *shared_to_feature_deep_imports,
                    *app_deep_module_imports,
                ]
            )
        ),
    }


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
    high_risk = [entry for entry in unmanaged if entry["severity"] == "high"]
    medium_risk = [entry for entry in unmanaged if entry["severity"] == "medium"]
    return {
        "open_count": len(open_entries),
        "unmanaged_feature_surface_count": len(unmanaged),
        "high_risk_unmanaged_feature_surface_count": len(high_risk),
        "high_risk_unmanaged_feature_surfaces": [entry["id"] for entry in high_risk],
        "medium_unmanaged_feature_surface_count": len(medium_risk),
        "medium_unmanaged_feature_surfaces": [entry["id"] for entry in medium_risk],
    }


def build_debt_inventory(repo_root: Path, generated_at: str | None = None) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    entries = _ownership_entries(repo_root)
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
            "classification_rule": "Every discovered zone is classified as canonical_feature_module, accepted_legacy_feature_boundary, unmanaged_feature_surface, shared_platform_infrastructure, compatibility_wrapper, runtime_process_ownership, or supporting_tool_test_documentation_frontend_evidence.",
        },
        "entries": entries,
        "summary": _debt_summary(entries),
        "overlapping_backend_app_python_files": _overlapping_backend_app_files(entries),
        "untracked_backend_app_python_files": _untracked_backend_app_files(repo_root, entries),
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
    ):
        return "RED"
    if debt_inventory["summary"]["high_risk_unmanaged_feature_surface_count"]:
        return "RED"
    if debt_inventory["summary"]["unmanaged_feature_surface_count"]:
        return "YELLOW"
    return "GREEN"


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
    if inventory_classification_issues:
        structure_001 = Finding(
            id="STRUCTURE-001",
            severity="high",
            status="open",
            area="backend-modules",
            finding="Backend has unclassified or overlapping production files in backend/app.",
            evidence=(
                f"app.modules.registry imports {', '.join(canonical_modules)}; "
                f"classification issues: {', '.join(inventory_classification_issues)}."
            ),
            risk="High. Architecture audit must not report overall backend GREEN while production files are unclassified or multiply owned.",
            recommendation="Classify each backend/app production file exactly once before merging.",
            suggested_phase="next",
        )
    elif summary["high_risk_unmanaged_feature_surface_count"]:
        structure_001 = Finding(
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
    elif summary["unmanaged_feature_surface_count"]:
        structure_001 = Finding(
            id="STRUCTURE-001",
            severity="medium",
            status="open",
            area="backend-modules",
            finding="Backend has canonical modules and only medium unmanaged feature surfaces remain outside app.modules.",
            evidence=(
                f"app.modules.registry imports {', '.join(canonical_modules)}; "
                "medium unmanaged feature surfaces: "
                f"{', '.join(summary['medium_unmanaged_feature_surfaces'])}."
            ),
            risk="Medium. Remaining feature debt is transitional and must stay visible until separately migrated or accepted.",
            recommendation="Continue with Phase 5 frontend/shared cleanup and Phase 6 account-platform debt split without hiding medium debt.",
            suggested_phase="Phase 5+",
        )
    else:
        structure_001 = Finding(
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

    if inventory_classification_issues:
        structure_008 = Finding(
            id="STRUCTURE-008",
            severity="high",
            status="open",
            area="unmanaged-backend-surfaces",
            finding="Machine-readable inventory found unclassified or overlapping backend/app production files.",
            evidence=json.dumps(
                {
                    "untracked_backend_app_python_files": debt_inventory[
                        "untracked_backend_app_python_files"
                    ],
                    "overlapping_backend_app_python_files": debt_inventory[
                        "overlapping_backend_app_python_files"
                    ],
                },
                sort_keys=True,
            ),
            risk="High if new feature-owned code can appear outside app.modules without exactly one inventory owner.",
            recommendation="Keep architecture debt inventory exhaustive and fail checks on untracked or overlapping backend/app production files.",
            suggested_phase="next",
        )
    elif summary["unmanaged_feature_surface_count"]:
        structure_008 = Finding(
            id="STRUCTURE-008",
            severity="high" if summary["high_risk_unmanaged_feature_surface_count"] else "medium",
            status="open",
            area="unmanaged-backend-surfaces",
            finding="Machine-readable inventory tracks backend/app feature surfaces outside canonical modules.",
            evidence=json.dumps(debt_inventory["summary"], sort_keys=True),
            risk="High if new feature-owned code can appear outside app.modules without being classified as debt or platform support; medium for current classified residual debt.",
            recommendation="Keep architecture debt inventory exhaustive and fail checks on untracked backend/app production files.",
            suggested_phase="Phase 0",
        )
    else:
        structure_008 = Finding(
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

    frontend_boundary_issues = [
        *frontend_boundaries["missing_indexes"],
        *frontend_boundaries["feature_to_feature_deep_imports"],
        *frontend_boundaries["shared_to_feature_deep_imports"],
        *frontend_boundaries["unexpected_shared_deep_imports"],
        *frontend_boundaries["unexpected_app_deep_module_imports"],
    ]
    if not frontend_boundaries["module_boundary_test"]:
        frontend_boundary_issues.append("module boundary test is missing")
    if frontend_boundaries["feature_modules"] != frontend_boundaries["expected_feature_modules"]:
        frontend_boundary_issues.append("feature module set differs from policy")
    frontend_finding = Finding(
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
        "findings": _findings(boundaries, forbidden_claims, debt_inventory, frontend_boundaries),
        "boundaries": boundaries,
        "workflows": workflows,
        "forbidden_runtime_claims": forbidden_claims,
        "recommended_next_phases": [
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
    if entry["category"] == "unmanaged_feature_surface":
        return "RED" if entry["severity"] == "high" else "YELLOW"
    if entry["status"] == "open":
        return "YELLOW"
    return "GREEN"


def _backend_overall_evidence(debt_summary: dict[str, Any]) -> str:
    high_count = debt_summary["high_risk_unmanaged_feature_surface_count"]
    medium_count = debt_summary["medium_unmanaged_feature_surface_count"]
    if high_count or medium_count:
        return (
            f"{high_count} high-risk and {medium_count} medium unmanaged feature surfaces remain."
        )
    return "No unmanaged feature debt remains."


def _backend_overall_risk(debt_summary: dict[str, Any]) -> str:
    if debt_summary["high_risk_unmanaged_feature_surface_count"]:
        return (
            "High-risk unmanaged feature surfaces must not be hidden behind overall backend health."
        )
    if debt_summary["medium_unmanaged_feature_surface_count"]:
        return "Architecture audit must not claim overall GREEN while classified medium or high unmanaged domains remain."
    return "Low while structure audit checks keep feature ownership classified."


def _backend_overall_followup(debt_summary: dict[str, Any]) -> str:
    if debt_summary["high_risk_unmanaged_feature_surface_count"]:
        return "Migrate or explicitly reclassify high-risk unmanaged feature surfaces."
    if debt_summary["medium_unmanaged_feature_surface_count"]:
        return "Keep medium debt visible while Phase 5/6 continue."
    return "Keep drift checks required for structural changes."


def _backend_modules_status(unmanaged_debt: list[dict[str, Any]]) -> str:
    return "YELLOW" if unmanaged_debt else "GREEN"


def _backend_modules_risk(unmanaged_debt: list[dict[str, Any]]) -> str:
    if unmanaged_debt:
        return "Canonical ownership exists for migrated modules only."
    return "Low while registered modules and support surfaces remain classified."


def _backend_modules_followup(unmanaged_debt: list[dict[str, Any]]) -> str:
    if unmanaged_debt:
        return "Continue with frontend/shared cleanup and account platform debt split."
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
    debt_entries = report["debt_inventory"]["entries"]
    debt_summary = report["debt_inventory"]["summary"]
    modules = report["modules"]
    runtime_roles = report["runtime_roles"]
    findings = report["findings"]
    frontend_boundaries = report["frontend_boundaries"]
    frontend_boundary_issues = [
        *frontend_boundaries["missing_indexes"],
        *frontend_boundaries["feature_to_feature_deep_imports"],
        *frontend_boundaries["shared_to_feature_deep_imports"],
        *frontend_boundaries["unexpected_shared_deep_imports"],
        *frontend_boundaries["unexpected_app_deep_module_imports"],
    ]
    high_debt = [
        entry
        for entry in debt_entries
        if entry["category"] == "unmanaged_feature_surface" and entry["severity"] == "high"
    ]
    unmanaged_debt = [
        entry for entry in debt_entries if entry["category"] == "unmanaged_feature_surface"
    ]
    unmanaged_status = "RED" if high_debt else "YELLOW" if unmanaged_debt else "GREEN"
    unmanaged_evidence = (
        ", ".join(entry["owner"] for entry in high_debt)
        if high_debt
        else ", ".join(entry["owner"] for entry in unmanaged_debt) or "No unmanaged feature debt."
    )
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
        "## 1. Executive Summary",
        "",
        _markdown_table(
            ("Area", "Status", "Evidence", "Risk", "Recommended follow-up"),
            [
                (
                    "Backend overall",
                    report["backend_overall_status"],
                    _backend_overall_evidence(debt_summary),
                    _backend_overall_risk(debt_summary),
                    _backend_overall_followup(debt_summary),
                ),
                (
                    "Backend modules",
                    _backend_modules_status(unmanaged_debt),
                    "Registered modules: "
                    + ", ".join(module["name"] for module in modules if module["registered"]),
                    _backend_modules_risk(unmanaged_debt),
                    _backend_modules_followup(unmanaged_debt),
                ),
                (
                    "Unmanaged feature debt",
                    unmanaged_status,
                    unmanaged_evidence,
                    _unmanaged_debt_risk(unmanaged_debt),
                    _unmanaged_debt_followup(unmanaged_debt),
                ),
                (
                    "Generated artifacts",
                    "GREEN",
                    "JSON, Markdown, and debt inventory render from one report pipeline.",
                    "Low while drift tests compare committed artifacts to deterministic renderers.",
                    "Run `python backend/scripts/structure_audit.py --check` after structural changes.",
                ),
                (
                    "Frontend ownership",
                    "RED" if frontend_boundary_issues else "GREEN",
                    "Feature modules: "
                    + ", ".join(frontend_boundaries["feature_modules"])
                    + "; accepted app compatibility deep imports: "
                    + str(len(frontend_boundaries["app_deep_module_imports"]))
                    + ".",
                    (
                        "Frontend module boundary violations are present."
                        if frontend_boundary_issues
                        else "Frontend public APIs are enforced; compatibility imports are explicit and bounded."
                    ),
                    (
                        "Remove unexpected deep imports or record them in the frontend boundary policy."
                        if frontend_boundary_issues
                        else "Keep frontend boundary policy checks required for module or wrapper changes."
                    ),
                ),
            ],
        ),
        "",
        "## 2. Backend Module Registry",
        "",
        _markdown_table(
            ("Module", "Registered", "Router", "Workflows", "Status"),
            [
                (
                    module["name"],
                    module["registered"],
                    module["router_path"] or "none",
                    ", ".join(
                        str(workflow.get("workflow_type")) for workflow in module["workflows"]
                    )
                    or "none",
                    "GREEN" if module["registered"] or module["documentation_only"] else "YELLOW",
                )
                for module in modules
            ],
        ),
        "",
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
                for entry in debt_entries
            ],
        ),
        "",
        "## 4. Required Unmanaged Domains",
        "",
        _markdown_table(
            ("Domain", "Severity", "Current paths", "Target owner", "Removal condition"),
            [
                (
                    entry["owner"],
                    entry["severity"],
                    "<br>".join(entry["paths"]),
                    entry["target_owner"],
                    entry["removal_condition"],
                )
                for entry in debt_entries
                if entry["category"] == "unmanaged_feature_surface"
            ],
        ),
        "",
        "## 5. Runtime / Process Structure",
        "",
        _markdown_table(
            ("Role", "Queues", "Live TDLib", "Notes"),
            [
                (
                    role["name"],
                    ", ".join(role.get("queues") or []) or "none",
                    "Yes" if role.get("allows_live_tdlib") else "No",
                    role.get("description") or "",
                )
                for role in runtime_roles
            ],
        ),
        "",
        "## 6. Architecture Guard Status",
        "",
        _markdown_table(
            ("Guard", "Status", "Evidence"),
            [
                (
                    "Untracked backend/app production files",
                    "GREEN"
                    if not report["debt_inventory"]["untracked_backend_app_python_files"]
                    and not report["debt_inventory"]["overlapping_backend_app_python_files"]
                    else "RED",
                    ", ".join(
                        [
                            *report["debt_inventory"]["untracked_backend_app_python_files"],
                            *report["debt_inventory"][
                                "overlapping_backend_app_python_files"
                            ].keys(),
                        ]
                    )
                    or "All backend/app Python files are classified exactly once by the inventory.",
                ),
                (
                    "Forbidden contract imports",
                    "GREEN"
                    if not any(report["boundaries"]["contracts_forbidden_imports"].values())
                    else "RED",
                    json.dumps(report["boundaries"]["contracts_forbidden_imports"], sort_keys=True),
                ),
                (
                    "Routers importing ORM models",
                    "GREEN"
                    if not any(report["boundaries"]["routers_importing_models"].values())
                    else "RED",
                    json.dumps(report["boundaries"]["routers_importing_models"], sort_keys=True),
                ),
                (
                    "Forbidden runtime claims",
                    "GREEN"
                    if report["forbidden_runtime_claims"] == {"queues": [], "workflows": []}
                    else "RED",
                    json.dumps(report["forbidden_runtime_claims"], sort_keys=True),
                ),
            ],
        ),
        "",
        "## 7. Frontend Boundary Policy",
        "",
        _markdown_table(
            ("Check", "Status", "Evidence"),
            [
                (
                    "Public module indexes",
                    "GREEN" if not frontend_boundaries["missing_indexes"] else "RED",
                    ", ".join(frontend_boundaries["missing_indexes"])
                    or "Every module has index.ts.",
                ),
                (
                    "Feature module set",
                    "GREEN"
                    if frontend_boundaries["feature_modules"]
                    == frontend_boundaries["expected_feature_modules"]
                    else "RED",
                    ", ".join(frontend_boundaries["feature_modules"]),
                ),
                (
                    "Feature to feature deep imports",
                    "GREEN"
                    if not frontend_boundaries["feature_to_feature_deep_imports"]
                    else "RED",
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
            ],
        ),
        "",
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
                for finding in findings
            ],
        ),
        "",
        "## 9. Recommended Next Implementation Issues",
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
    return "\n".join(lines)


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
