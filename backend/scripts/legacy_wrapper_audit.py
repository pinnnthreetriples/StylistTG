from __future__ import annotations

import ast
import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WrapperSpec:
    legacy_path: str
    file: str
    canonical_owner: str
    allowed_importers: tuple[str, ...]
    forbidden_importers: tuple[str, ...]
    notes: str


_NEURO_COMMENTING_SERVICE_MODULES = (
    "account_health_service",
    "account_selector",
    "ai_comment_generator",
    "ai_provider_openai",
    "analytics_service",
    "approval_expirer",
    "approval_service",
    "campaign_account_service",
    "campaign_service",
    "channel_rules_service",
    "discussion_resolver",
    "enums",
    "errors",
    "limits_service",
    "live_readiness_service",
    "post_context_builder",
    "post_detector",
    "prompt_builder",
    "prompt_presets",
    "rate_limiter",
    "repository",
    "rules_policy",
    "safety_policy",
    "sender_service",
    "target_health_service",
    "target_service",
    "tdlib_comment_sender",
    "tdlib_helpers",
    "tdlib_observer",
    "tdlib_runtime",
)


def _neuro_commenting_service_wrapper(
    module_name: str, *, canonical_module: str | None = None
) -> WrapperSpec:
    canonical = canonical_module or f"app.modules.neuro_commenting.{module_name}"
    return WrapperSpec(
        legacy_path=f"app.services.neuro_commenting.{module_name}",
        file=f"backend/app/services/neuro_commenting/{module_name}.py",
        canonical_owner=canonical,
        allowed_importers=("tests", "external_compatibility"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves old neuro-commenting service imports while implementation is module-owned.",
    )


_ACCOUNT_SAFETY_WRAPPERS = (
    (
        "app.api.account_quarantine_routes",
        "backend/app/api/account_quarantine_routes.py",
        "app.modules.account_safety.quarantine_router",
        "Preserves legacy account quarantine router import path.",
    ),
    (
        "app.api.account_runtime_routes",
        "backend/app/api/account_runtime_routes.py",
        "app.modules.account_safety.runtime_router",
        "Preserves legacy account runtime router import path.",
    ),
    (
        "app.api.account_safety_routes",
        "backend/app/api/account_safety_routes.py",
        "app.modules.account_safety.accounts_router",
        "Preserves legacy account-safety accounts router import path.",
    ),
    (
        "app.api.account_status_routes",
        "backend/app/api/account_status_routes.py",
        "app.modules.account_safety.status_router",
        "Preserves legacy account status router import path.",
    ),
    (
        "app.contracts.account_status",
        "backend/app/contracts/account_status.py",
        "app.modules.account_safety.status_contracts",
        "Preserves old account status contract imports.",
    ),
    (
        "app.contracts.quarantine",
        "backend/app/contracts/quarantine.py",
        "app.modules.account_safety.quarantine_contracts",
        "Preserves old account quarantine contract imports.",
    ),
    (
        "app.api.safety_policy",
        "backend/app/api/safety_policy.py",
        "app.modules.account_safety.policy_router",
        "Preserves legacy workspace safety policy router import path.",
    ),
    (
        "app.contracts.safety",
        "backend/app/contracts/safety.py",
        "app.modules.account_safety.read_contracts",
        "Preserves old account safety read contract imports.",
    ),
    (
        "app.contracts.safety_gate",
        "backend/app/contracts/safety_gate.py",
        "app.modules.account_safety.gate_contracts",
        "Preserves old account safety gate contract imports.",
    ),
    (
        "app.services.account_batch_safety",
        "backend/app/services/account_batch_safety.py",
        "app.modules.account_safety.batch_preview",
        "Preserves old account batch safety preview service imports.",
    ),
    (
        "app.services.account_cooldowns",
        "backend/app/services/account_cooldowns.py",
        "app.modules.account_safety.cooldowns",
        "Preserves old account cooldown service imports.",
    ),
    (
        "app.services.account_health",
        "backend/app/services/account_health.py",
        "app.modules.account_safety.health",
        "Preserves old account health service imports.",
    ),
    (
        "app.services.account_quarantine",
        "backend/app/services/account_quarantine.py",
        "app.modules.account_safety.quarantine",
        "Preserves old account quarantine service imports.",
    ),
    (
        "app.services.account_risk",
        "backend/app/services/account_risk.py",
        "app.modules.account_safety.risk",
        "Preserves old account risk service imports.",
    ),
    (
        "app.services.account_safety",
        "backend/app/services/account_safety.py",
        "app.modules.account_safety.read_models",
        "Preserves old account safety read model service imports.",
    ),
    (
        "app.services.account_safety_gate",
        "backend/app/services/account_safety_gate.py",
        "app.modules.account_safety.gate",
        "Preserves old account safety gate service imports.",
    ),
    (
        "app.services.account_safety_overrides",
        "backend/app/services/account_safety_overrides.py",
        "app.modules.account_safety.overrides",
        "Preserves old account safety override service imports.",
    ),
    (
        "app.services.account_status_monitor",
        "backend/app/services/account_status_monitor.py",
        "app.modules.account_safety.status_monitor",
        "Preserves old account status monitor service imports.",
    ),
    (
        "app.services.account_terminal_status",
        "backend/app/services/account_terminal_status.py",
        "app.modules.account_safety.terminal_status",
        "Preserves old account terminal status service imports.",
    ),
    (
        "app.services.account_validity",
        "backend/app/services/account_validity.py",
        "app.modules.account_safety.validity",
        "Preserves old account validity service imports.",
    ),
    (
        "app.services.risk_gate",
        "backend/app/services/risk_gate.py",
        "app.modules.account_safety.action_gate",
        "Preserves old account action gate service imports.",
    ),
    (
        "app.services.safety_gate_cache",
        "backend/app/services/safety_gate_cache.py",
        "app.modules.account_safety.cache",
        "Preserves old account safety gate cache imports.",
    ),
    (
        "app.services.safety_gate_reserve",
        "backend/app/services/safety_gate_reserve.py",
        "app.modules.account_safety.reserve",
        "Preserves old account safety gate reservation imports.",
    ),
    (
        "app.services.workspace_safety_policy",
        "backend/app/services/workspace_safety_policy.py",
        "app.modules.account_safety.policy",
        "Preserves old workspace safety policy service imports.",
    ),
)


_ACCOUNT_LIFECYCLE_WRAPPERS = (
    (
        "app.api.account_lifecycle_routes",
        "backend/app/api/account_lifecycle_routes.py",
        "app.modules.account_lifecycle.router",
        "Preserves legacy account lifecycle router import path.",
    ),
    (
        "app.services.account_lifecycle",
        "backend/app/services/account_lifecycle.py",
        "app.modules.account_lifecycle.service",
        "Preserves old account lifecycle service imports.",
    ),
    (
        "app.services.retention_worker",
        "backend/app/services/retention_worker.py",
        "app.modules.account_lifecycle.retention",
        "Preserves old retention worker imports.",
    ),
)

_ACCOUNT_PROFILE_COMPLETENESS_WRAPPERS = (
    (
        "app.api.account_profile_completeness_routes",
        "backend/app/api/account_profile_completeness_routes.py",
        "app.modules.account_profile_completeness.router",
        "Preserves legacy account profile-completeness router import path.",
    ),
    (
        "app.contracts.profile_completeness",
        "backend/app/contracts/profile_completeness.py",
        "app.modules.account_profile_completeness.contracts",
        "Preserves old account profile-completeness contract imports.",
    ),
    (
        "app.services.account_profile_completeness",
        "backend/app/services/account_profile_completeness.py",
        "app.modules.account_profile_completeness.service",
        "Preserves old account profile-completeness service imports.",
    ),
)


_ACCOUNT_OPERATIONS_WRAPPERS = (
    (
        "app.api.account_audit_routes",
        "backend/app/api/account_audit_routes.py",
        "app.modules.account_audit.router",
        "Preserves legacy account audit router import path.",
    ),
    (
        "app.api.account_compat_routes",
        "backend/app/api/account_compat_routes.py",
        "app.modules.account_core.compat_router",
        "Preserves legacy account compatibility router import path.",
    ),
    (
        "app.api.account_context",
        "backend/app/api/account_context.py",
        "app.modules.account_core.context",
        "Preserves legacy account context import path.",
    ),
    (
        "app.api.account_imports",
        "backend/app/api/account_imports.py",
        "app.modules.account_imports.router",
        "Preserves legacy account imports router import path.",
    ),
    (
        "app.api.account_jobs_routes",
        "backend/app/api/account_jobs_routes.py",
        "app.modules.account_jobs.router",
        "Preserves legacy account jobs router import path.",
    ),
    (
        "app.api.account_proxy_routes",
        "backend/app/api/account_proxy_routes.py",
        "app.modules.account_proxy.router",
        "Preserves legacy account proxy router import path.",
    ),
    (
        "app.api.accounts",
        "backend/app/api/accounts.py",
        "app.modules.account_core.accounts_router",
        "Preserves legacy accounts router import path.",
    ),
    (
        "app.contracts.accounts",
        "backend/app/contracts/accounts.py",
        "app.modules.account_core.account_contracts",
        "Preserves legacy account contract imports.",
    ),
    (
        "app.contracts.cross_module_load",
        "backend/app/contracts/cross_module_load.py",
        "app.modules.account_core.cross_module_contracts",
        "Preserves legacy cross-module load contract imports.",
    ),
    (
        "app.services.account_bundle",
        "backend/app/services/account_bundle.py",
        "app.modules.account_core.bundle",
        "Preserves legacy account bundle service imports.",
    ),
    (
        "app.services.account_imports",
        "backend/app/services/account_imports.py",
        "app.modules.account_imports.service",
        "Preserves legacy account imports service imports.",
    ),
    (
        "app.services.proxy_accounts",
        "backend/app/services/proxy_accounts.py",
        "app.modules.account_proxy.accounts",
        "Preserves legacy account proxy service imports.",
    ),
    (
        "app.services.proxy_checks",
        "backend/app/services/proxy_checks.py",
        "app.modules.account_proxy.checks",
        "Preserves legacy proxy check service imports.",
    ),
)


def _account_safety_wrapper(
    legacy_path: str,
    file: str,
    canonical_owner: str,
    notes: str,
) -> WrapperSpec:
    return WrapperSpec(
        legacy_path=legacy_path,
        file=file,
        canonical_owner=canonical_owner,
        allowed_importers=("tests", "external_compatibility"),
        forbidden_importers=("backend/app/modules",),
        notes=notes,
    )


def _account_transitional_wrapper(
    legacy_path: str,
    file: str,
    canonical_owner: str,
    notes: str,
) -> WrapperSpec:
    return WrapperSpec(
        legacy_path=legacy_path,
        file=file,
        canonical_owner=canonical_owner,
        allowed_importers=("tests", "external_compatibility", "backend/app/modules"),
        forbidden_importers=(),
        notes=notes,
    )


WRAPPERS = (
    WrapperSpec(
        legacy_path="app.api.account_update",
        file="backend/app/api/account_update.py",
        canonical_owner="app.modules.account_editing.router",
        allowed_importers=("tests", "external_compatibility"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves legacy router import path for /api/account-update.",
    ),
    WrapperSpec(
        legacy_path="app.api.neuro_commenting",
        file="backend/app/api/neuro_commenting.py",
        canonical_owner="app.modules.neuro_commenting.router",
        allowed_importers=("tests", "external_compatibility"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves legacy router import path for /api/neuro-commenting.",
    ),
    *(_account_safety_wrapper(*wrapper) for wrapper in _ACCOUNT_SAFETY_WRAPPERS),
    *(_account_safety_wrapper(*wrapper) for wrapper in _ACCOUNT_LIFECYCLE_WRAPPERS),
    *(_account_safety_wrapper(*wrapper) for wrapper in _ACCOUNT_PROFILE_COMPLETENESS_WRAPPERS),
    *(_account_safety_wrapper(*wrapper) for wrapper in _ACCOUNT_OPERATIONS_WRAPPERS),
    _account_transitional_wrapper(
        "app.services.accounts",
        "backend/app/services/accounts.py",
        "app.modules.account_core.service",
        "Preserves legacy account CRUD service imports while module callers transition off the wrapper.",
    ),
    _account_transitional_wrapper(
        "app.services.account_capabilities",
        "backend/app/services/account_capabilities.py",
        "app.modules.account_core.capabilities",
        "Preserves legacy account capabilities service imports while module callers transition off the wrapper.",
    ),
    WrapperSpec(
        legacy_path="app.api.warmup",
        file="backend/app/api/warmup.py",
        canonical_owner="app.modules.warmup.router",
        allowed_importers=("tests", "external_compatibility"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves legacy router import path for /api/warmup.",
    ),
    WrapperSpec(
        legacy_path="app.services.account_update_jobs",
        file="backend/app/services/account_update_jobs.py",
        canonical_owner="app.modules.account_editing.service",
        allowed_importers=("tests", "external_compatibility"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves old account update preview/job service imports.",
    ),
    WrapperSpec(
        legacy_path="app.services.account_update_plan",
        file="backend/app/services/account_update_plan.py",
        canonical_owner="app.modules.account_editing.planner",
        allowed_importers=("tests", "external_compatibility"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves old account update planner imports.",
    ),
    WrapperSpec(
        legacy_path="app.services.auth_context",
        file="backend/app/services/auth_context.py",
        canonical_owner="app.modules.auth.dependencies / context",
        allowed_importers=("tests", "external_compatibility", "backend/app/api"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves existing auth dependency imports and override keys.",
    ),
    WrapperSpec(
        legacy_path="app.services.neuro_commenting",
        file="backend/app/services/neuro_commenting/__init__.py",
        canonical_owner="app.modules.neuro_commenting",
        allowed_importers=("tests", "external_compatibility"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves old neuro-commenting package imports while implementation is module-owned.",
    ),
    *(
        _neuro_commenting_service_wrapper(module_name)
        for module_name in _NEURO_COMMENTING_SERVICE_MODULES
    ),
    _neuro_commenting_service_wrapper(
        "jobs", canonical_module="app.modules.neuro_commenting.job_handlers"
    ),
    WrapperSpec(
        legacy_path="app.services.warmup",
        file="backend/app/services/warmup.py",
        canonical_owner="app.modules.warmup.service",
        allowed_importers=("tests", "external_compatibility"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves old warmup service imports.",
    ),
    WrapperSpec(
        legacy_path="app.services.warmup_dispatch",
        file="backend/app/services/warmup_dispatch.py",
        canonical_owner="app.modules.warmup.dispatcher",
        allowed_importers=("tests", "external_compatibility"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves old warmup dispatch service imports.",
    ),
    WrapperSpec(
        legacy_path="app.services.warmup_isolation",
        file="backend/app/services/warmup_isolation.py",
        canonical_owner="app.modules.warmup.isolation",
        allowed_importers=("tests", "external_compatibility"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves old warmup isolation imports.",
    ),
    WrapperSpec(
        legacy_path="app.services.warmup_p2p",
        file="backend/app/services/warmup_p2p.py",
        canonical_owner="app.modules.warmup.p2p",
        allowed_importers=("tests", "external_compatibility"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves old warmup peer selection imports.",
    ),
    WrapperSpec(
        legacy_path="app.services.warmup_readiness",
        file="backend/app/services/warmup_readiness.py",
        canonical_owner="app.modules.warmup.readiness",
        allowed_importers=("tests", "external_compatibility"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves old warmup readiness imports.",
    ),
    WrapperSpec(
        legacy_path="app.services.warmup_worker",
        file="backend/app/services/warmup_worker.py",
        canonical_owner="app.modules.warmup.worker",
        allowed_importers=("tests", "external_compatibility"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves old warmup due-session worker service imports.",
    ),
    WrapperSpec(
        legacy_path="app.services.workspaces",
        file="backend/app/services/workspaces.py",
        canonical_owner="app.workspace_bootstrap",
        allowed_importers=("tests", "external_compatibility"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves old local default workspace bootstrap service imports.",
    ),
    WrapperSpec(
        legacy_path="app.workers.account_update_jobs",
        file="backend/app/workers/account_update_jobs.py",
        canonical_owner="app.modules.account_editing.executor",
        allowed_importers=("tests", "external_compatibility"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves old RQ worker import path.",
    ),
    WrapperSpec(
        legacy_path="app.workers.warmup_dispatch_jobs",
        file="backend/app/workers/warmup_dispatch_jobs.py",
        canonical_owner="app.modules.warmup.jobs",
        allowed_importers=("tests", "external_compatibility", "workflow_registry"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves old warmup dispatch worker import path.",
    ),
    WrapperSpec(
        legacy_path="app.workers.warmup_jobs",
        file="backend/app/workers/warmup_jobs.py",
        canonical_owner="app.modules.warmup.jobs",
        allowed_importers=("tests", "external_compatibility", "workflow_registry"),
        forbidden_importers=("backend/app/modules",),
        notes="Preserves old warmup due-session worker import path.",
    ),
)

VALID_STAGES = {
    "stage_0_compatibility_active",
    "stage_1_no_new_imports",
    "stage_2_internal_call_sites_migrated",
    "stage_3_tests_migrated",
    "stage_4_external_import_risk_assessed",
    "stage_5_wrapper_removal_pr",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_manifest(generated_at: str | None = None) -> dict[str, Any]:
    return {
        "generated_at": generated_at or _utc_timestamp(),
        "wrappers": [
            {
                "legacy_path": spec.legacy_path,
                "file": spec.file,
                "canonical_owner": spec.canonical_owner,
                "stage": "stage_0_compatibility_active",
                "allowed_importers": list(spec.allowed_importers),
                "forbidden_importers": list(spec.forbidden_importers),
                "removal_blockers": [],
                "notes": spec.notes,
            }
            for spec in sorted(WRAPPERS, key=lambda item: item.legacy_path)
        ],
    }


def _python_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _matches(imported: str, legacy_path: str) -> bool:
    return imported == legacy_path or imported.startswith(f"{legacy_path}.")


def validate_manifest(repo: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = build_manifest(generated_at=str(manifest.get("generated_at", "")))
    if manifest != expected:
        errors.append("docs/architecture/legacy-wrappers.json does not match generated manifest")

    for wrapper in manifest.get("wrappers", []):
        stage = wrapper.get("stage")
        if stage not in VALID_STAGES:
            errors.append(f"{wrapper.get('legacy_path')} uses invalid stage {stage!r}")

        path = repo / str(wrapper.get("file", ""))
        if not path.exists():
            errors.append(f"wrapper file missing: {path}")
            continue

        source = path.read_text(encoding="utf-8")
        canonical_owner = wrapper.get("canonical_owner")
        if "Compatibility wrapper." not in source:
            errors.append(f"{path} is missing compatibility docstring")
        if f"Canonical owner: {canonical_owner}" not in source:
            errors.append(f"{path} is missing canonical owner marker {canonical_owner!r}")
        if "Do not add new behavior here." not in source:
            errors.append(f"{path} is missing no-new-behavior marker")

    legacy_paths = [
        wrapper["legacy_path"]
        for wrapper in expected["wrappers"]
        if "backend/app/modules" in wrapper.get("forbidden_importers", [])
    ]
    for source in _python_files(repo / "backend/app/modules"):
        for imported in _imports(source):
            if any(_matches(imported, legacy_path) for legacy_path in legacy_paths):
                errors.append(f"module imports legacy wrapper: {source} imports {imported}")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate the legacy wrapper deprecation manifest."
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="print the deterministic manifest to stdout instead of validating the committed file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="write a generated manifest to the given path",
    )
    args = parser.parse_args()

    repo = repo_root()
    manifest_path = repo / "docs/architecture/legacy-wrappers.json"
    if args.output:
        manifest = build_manifest()
        output = args.output if args.output.is_absolute() else repo / args.output
        output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Wrote {output.relative_to(repo).as_posix()}")
        return
    if args.print:
        print(json.dumps(build_manifest(), indent=2, sort_keys=True))
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = validate_manifest(repo, manifest)
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Validated {manifest_path.relative_to(repo).as_posix()}")


if __name__ == "__main__":
    main()
