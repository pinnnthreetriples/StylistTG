from __future__ import annotations

import ast
import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GENERATED_AT = "2026-05-17T00:00:00Z"


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
        "app.api.account_safety_routes",
        "backend/app/api/account_safety_routes.py",
        "app.modules.account_safety.accounts_router",
        "Preserves legacy account-safety accounts router import path.",
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


def build_manifest() -> dict[str, Any]:
    return {
        "generated_at": GENERATED_AT,
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
    expected = build_manifest()
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

    legacy_paths = [wrapper["legacy_path"] for wrapper in expected["wrappers"]]
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
    args = parser.parse_args()

    repo = repo_root()
    manifest_path = repo / "docs/architecture/legacy-wrappers.json"
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
