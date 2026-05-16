from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

GENERATED_AT = "2026-05-17T00:00:00Z"

MODULES_ROOT = Path("backend/app/modules")
RUNTIME_ROOT = Path("backend/app/runtime")
FRONTEND_MODULES_ROOT = Path("apps/dashboard/src/modules")

WRAPPER_PATHS = (
    "backend/app/api/account_update.py",
    "backend/app/api/warmup.py",
    "backend/app/services/account_update_jobs.py",
    "backend/app/services/account_update_plan.py",
    "backend/app/workers/account_update_jobs.py",
    "backend/app/services/auth_context.py",
    "backend/app/services/warmup.py",
    "backend/app/services/warmup_worker.py",
    "backend/app/services/warmup_dispatch.py",
    "backend/app/services/warmup_isolation.py",
    "backend/app/services/warmup_readiness.py",
    "backend/app/services/warmup_p2p.py",
    "backend/app/workers/warmup_jobs.py",
    "backend/app/workers/warmup_dispatch_jobs.py",
)

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
    "sqlalchemy",
    "app.db",
    "app.api",
    "fastapi",
    "redis",
    "rq",
)
FORBIDDEN_REPOSITORY_IMPORTS = ("fastapi", "app.api", "app.main")


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


def _read_text(repo_root: Path, relative_path: str) -> str:
    path = repo_root / relative_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _relative(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _parse_ast(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
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


def _literal_value(node: ast.AST, constants: dict[str, str]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id, node.id)
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
    constants = _string_assignments(repo_root / "backend/app/services/worker_plane.py")
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
                "has_router": (module_dir / "router.py").exists(),
                "has_service_facade": (module_dir / "service.py").exists(),
                "has_repository": (module_dir / "repository.py").exists(),
                "has_policies": (module_dir / "policies.py").exists(),
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
    worker_constants = _string_assignments(repo_root / "backend/app/services/worker_plane.py")
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
    constants = _string_assignments(repo_root / "backend/app/services/worker_plane.py")
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
        text = path.read_text(encoding="utf-8")
        if import_path in text:
            references.append(_relative(path, repo_root))
    return sorted(references)


def _audit_legacy_wrappers(repo_root: Path) -> list[dict[str, Any]]:
    audit_doc = _read_text(repo_root, "docs/architecture/legacy-wrapper-audit.md")
    wrappers: list[dict[str, Any]] = []
    for wrapper in WRAPPER_PATHS:
        path = repo_root / wrapper
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        canonical_match = re.search(r"Canonical owner:\s*([^\n]+)", text)
        import_path = wrapper.removeprefix("backend/").removesuffix(".py").replace("/", ".")
        wrappers.append(
            {
                "path": wrapper,
                "import_path": import_path,
                "exists": path.exists(),
                "docstring_present": '"""Compatibility wrapper.' in text,
                "canonical_owner": canonical_match.group(1).strip() if canonical_match else None,
                "do_not_add_behavior_marker": "Do not add new behavior here." in text,
                "documented_in_audit": import_path in audit_doc or wrapper in audit_doc,
                "module_import_references": _module_import_references(repo_root, import_path),
            }
        )
    return wrappers


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


def _audit_security_checks(repo_root: Path) -> list[dict[str, Any]]:
    workflow_map = {
        "CI": ".github/workflows/ci.yml",
        "Test Quality": ".github/workflows/test-quality.yml",
        "Semgrep": ".github/workflows/semgrep.yml",
        "Secret Scan": ".github/workflows/secret-scan.yml",
        "SBOM": ".github/workflows/sbom.yml",
        "Container Scan": ".github/workflows/container-scan.yml",
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
    contract_files.append(repo_root / "backend/app/schemas.py")
    policy_files = sorted((repo_root / MODULES_ROOT).glob("*/policies.py"))
    repository_files = sorted((repo_root / MODULES_ROOT).glob("*/repository.py"))
    router_files = sorted((repo_root / MODULES_ROOT).glob("*/router.py"))

    fastapi_violations: list[str] = []
    for path in _python_files(repo_root / MODULES_ROOT):
        rel = _relative(path, repo_root)
        if rel.endswith("/router.py") or rel.endswith("/auth/dependencies.py"):
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


def _findings(
    boundaries: dict[str, Any], forbidden_claims: dict[str, list[str]]
) -> list[dict[str, str]]:
    findings = [
        Finding(
            id="STRUCTURE-001",
            severity="info",
            status="accepted",
            area="backend-modules",
            finding="Backend module registry has auth, account_editing, and warmup as canonical modules.",
            evidence="app.modules.registry imports auth, account_editing, and warmup; _template remains documentation-only.",
            risk="Low. The main feature module boundary is explicit and enforced by architecture tests.",
            recommendation="Continue adding new product modules through the documented module checklist.",
            suggested_phase="ongoing",
        ),
        Finding(
            id="STRUCTURE-002",
            severity="medium",
            status="open",
            area="frontend",
            finding="Frontend modularization is started, but global lib, hooks, components, and features still own substantial feature logic.",
            evidence="apps/dashboard/src/modules has account-editing, auth, and warmup indexes; global dashboard roots still contain many files.",
            risk="Future frontend work can bypass module boundaries unless feature ownership keeps moving behind public module indexes.",
            recommendation="Move feature-specific dashboard helpers/components into modules in small compatibility-preserving passes.",
            suggested_phase="Phase 23",
        ),
        Finding(
            id="STRUCTURE-003",
            severity="medium",
            status="deferred",
            area="storage-contracts",
            finding="app.models.py remains global and app.schemas.py remains a compatibility/global DTO layer.",
            evidence="Storage boundary docs intentionally defer app.models split and shared contracts extraction.",
            risk="New code may import global ORM or DTO layers unless architecture tests keep blocking the highest-risk paths.",
            recommendation="Extract shared contracts and continue moving ORM access behind repositories before splitting app.models.",
            suggested_phase="Phase 24",
        ),
        Finding(
            id="STRUCTURE-004",
            severity="low",
            status="accepted",
            area="legacy-wrappers",
            finding="Legacy API/service/worker wrappers remain import-compatible by design.",
            evidence="Wrappers include compatibility docstrings and are documented in legacy-wrapper-audit.md.",
            risk="Low while architecture tests prevent modules from importing legacy wrappers.",
            recommendation="Define removal readiness and downstream call-site migration criteria.",
            suggested_phase="Phase 25",
        ),
        Finding(
            id="STRUCTURE-005",
            severity="low",
            status="deferred",
            area="runtime",
            finding="maintenance_worker temporarily owns reserved media, story, and account-lifecycle queues.",
            evidence="Runtime role metadata assigns reserved queues to maintenance_worker until dedicated roles are justified.",
            risk="Moderate future blast-radius risk if those queues become active without a role split.",
            recommendation="Introduce dedicated roles once media/story/lifecycle execution becomes active production work.",
            suggested_phase="Phase 26",
        ),
        Finding(
            id="STRUCTURE-006",
            severity="low",
            status="open",
            area="architecture-tests",
            finding="Architecture tests contain duplicated static-analysis helper patterns.",
            evidence="Multiple tests parse imports and source files independently with small local helper functions.",
            risk="Low. Duplication can make future boundary-rule changes noisy.",
            recommendation="Consolidate AST/import helper utilities after the boundary set stabilizes.",
            suggested_phase="Phase 23+",
        ),
        Finding(
            id="STRUCTURE-007",
            severity="info",
            status="accepted",
            area="security",
            finding="Security baseline workflows and documentation are present.",
            evidence="CI, Test Quality, Semgrep, Secret Scan, SBOM, Container Scan, Trivy, Complexity, Gitleaks config, and security docs exist.",
            risk="Low. Branch protection remains a repository setting outside source control.",
            recommendation="Keep security docs in sync with GitHub branch protection and workflow policy changes.",
            suggested_phase="ongoing",
        ),
    ]
    if any(boundaries["contracts_forbidden_imports"].values()) or any(
        boundaries["routers_importing_models"].values()
    ):
        findings.append(
            Finding(
                id="STRUCTURE-008",
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
                id="STRUCTURE-009",
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


def build_report(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    modules = _audit_modules(repo_root)
    runtime_roles = _audit_runtime_roles(repo_root)
    queues = _audit_queues(repo_root, runtime_roles)
    workflows = _workflow_specs(repo_root)
    boundaries = _audit_boundaries(repo_root)
    forbidden_claims = _forbidden_runtime_claims(workflows, queues)
    return {
        "generated_at": GENERATED_AT,
        "modules": modules,
        "runtime_roles": runtime_roles,
        "queues": queues,
        "legacy_wrappers": _audit_legacy_wrappers(repo_root),
        "architecture_tests": _audit_architecture_tests(repo_root),
        "frontend_modules": _audit_frontend_modules(repo_root),
        "security_checks": _audit_security_checks(repo_root),
        "findings": _findings(boundaries, forbidden_claims),
        "boundaries": boundaries,
        "workflows": workflows,
        "forbidden_runtime_claims": forbidden_claims,
        "recommended_next_phases": [
            "Phase 23 - Frontend feature ownership cleanup",
            "Phase 24 - Shared contracts extraction",
            "Phase 25 - Legacy wrappers deprecation plan",
            "Phase 26 - Dedicated runtime roles for maintenance/media/story/lifecycle",
            "Phase 27 - First new module: analytics read-only or broadcast preview-only",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the static project structure audit report.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path. Defaults to docs/architecture/structure-audit.json.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    output = args.output or repo_root / "docs/architecture/structure-audit.json"
    if not output.is_absolute():
        output = repo_root / output
    report = build_report(repo_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
