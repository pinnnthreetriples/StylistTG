from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
SCRIPTS_ROOT = BACKEND_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from structure_audit import (  # noqa: E402
    _backend_overall_status,
    _debt_summary,
    _findings,
    _residual_boundary_guard,
    build_report,
    detect_report_drift,
    render_debt_inventory,
    render_json_report,
    render_markdown_report,
    write_report_artifacts,
)


REPORT_PATH = REPO_ROOT / "docs/architecture/structure-audit.json"
MARKDOWN_REPORT_PATH = REPO_ROOT / "docs/architecture/STRUCTURE_AUDIT.md"
DEBT_INVENTORY_PATH = REPO_ROOT / "docs/architecture/architecture-debt-inventory.json"
RESIDUAL_MANIFEST_PATH = REPO_ROOT / "docs/architecture/residual-legacy-boundaries.json"
REQUIRED_KEYS = {
    "schema_version",
    "generated_at",
    "backend_overall_status",
    "modules",
    "runtime_roles",
    "queues",
    "legacy_wrappers",
    "architecture_tests",
    "frontend_modules",
    "frontend_boundaries",
    "debt_inventory",
    "security_checks",
    "findings",
}


def _committed_report() -> dict[str, object]:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def _report_with_unmanaged_entries(
    base_report: dict[str, Any],
    unmanaged_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    report = deepcopy(base_report)
    non_unmanaged = [
        entry
        for entry in report["debt_inventory"]["entries"]
        if entry["category"] != "unmanaged_feature_surface"
    ]
    report["debt_inventory"]["entries"] = [*non_unmanaged, *unmanaged_entries]
    report["debt_inventory"]["summary"] = _debt_summary(report["debt_inventory"]["entries"])
    report["backend_overall_status"] = _backend_overall_status(report["debt_inventory"])
    report["findings"] = _findings(
        report["boundaries"],
        report["forbidden_runtime_claims"],
        report["debt_inventory"],
        report["frontend_boundaries"],
    )
    return report


def _report_with_open_debt_entries(
    base_report: dict[str, Any],
    *,
    unmanaged_entries: list[dict[str, Any]] | None = None,
    residual_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    report = deepcopy(base_report)
    filtered = [
        entry
        for entry in report["debt_inventory"]["entries"]
        if entry["category"]
        not in {"unmanaged_feature_surface", "residual_legacy_feature_boundary"}
    ]
    report["debt_inventory"]["entries"] = [
        *filtered,
        *(unmanaged_entries or []),
        *(residual_entries or []),
    ]
    report["debt_inventory"]["summary"] = _debt_summary(report["debt_inventory"]["entries"])
    report["debt_inventory"]["residual_boundary_guard"] = {
        **report["debt_inventory"]["residual_boundary_guard"],
        "boundary_count": len(residual_entries or []),
        "violations": [],
    }
    report["backend_overall_status"] = _backend_overall_status(report["debt_inventory"])
    report["findings"] = _findings(
        report["boundaries"],
        report["forbidden_runtime_claims"],
        report["debt_inventory"],
        report["frontend_boundaries"],
    )
    return report


def _unmanaged_entry(
    *,
    entry_id: str,
    owner: str,
    severity: str,
) -> dict[str, Any]:
    return {
        "id": entry_id,
        "category": "unmanaged_feature_surface",
        "severity": severity,
        "status": "open",
        "owner": owner,
        "paths": [f"backend/app/api/{owner}.py"],
        "existing_paths": [f"backend/app/api/{owner}.py"],
        "target_owner": f"app.modules.{owner}",
        "phase": "synthetic-test",
        "removal_condition": "Synthetic scenario exits when the owner is migrated.",
        "rationale": "Synthetic scenario coverage entry.",
    }


def _residual_entry(*, entry_id: str, owner: str) -> dict[str, Any]:
    return {
        "id": entry_id,
        "category": "residual_legacy_feature_boundary",
        "severity": "medium",
        "status": "open",
        "owner": owner,
        "paths": [f"backend/app/api/{owner}.py"],
        "existing_paths": [f"backend/app/api/{owner}.py"],
        "target_owner": f"app.modules.{owner} (follow-up #999)",
        "phase": "synthetic-test",
        "removal_condition": "Synthetic residual exits when the owner is migrated.",
        "rationale": "Synthetic residual boundary coverage entry.",
    }


def test_structure_audit_report_matches_static_script() -> None:
    report = _committed_report()
    assert REPORT_PATH.read_text(encoding="utf-8") == render_json_report(
        build_report(REPO_ROOT, generated_at=str(report["generated_at"]))
    )


def test_structure_audit_generated_at_can_be_injected() -> None:
    report = build_report(REPO_ROOT, generated_at="2026-05-26T10:11:12Z")

    assert report["generated_at"] == "2026-05-26T10:11:12Z"


def test_structure_audit_markdown_matches_static_renderer() -> None:
    report = _committed_report()
    expected = render_markdown_report(
        build_report(REPO_ROOT, generated_at=str(report["generated_at"]))
    )

    assert MARKDOWN_REPORT_PATH.read_text(encoding="utf-8") == expected


def test_structure_audit_debt_inventory_matches_static_renderer() -> None:
    report = _committed_report()
    expected = render_debt_inventory(
        build_report(REPO_ROOT, generated_at=str(report["generated_at"]))
    )

    assert DEBT_INVENTORY_PATH.read_text(encoding="utf-8") == expected


def test_structure_audit_drift_check_passes_for_committed_artifacts() -> None:
    assert detect_report_drift(REPO_ROOT) == []


def test_structure_audit_drift_check_detects_json_drift(tmp_path: Path) -> None:
    report = _committed_report()
    expected = build_report(REPO_ROOT, generated_at=str(report["generated_at"]))
    json_path = tmp_path / "structure-audit.json"
    markdown_path = tmp_path / "STRUCTURE_AUDIT.md"
    debt_path = tmp_path / "architecture-debt-inventory.json"
    json_path.write_text(
        render_json_report({**expected, "backend_overall_status": "RED"}), encoding="utf-8"
    )
    markdown_path.write_text(render_markdown_report(expected), encoding="utf-8")
    debt_path.write_text(render_debt_inventory(expected), encoding="utf-8")

    assert detect_report_drift(REPO_ROOT, json_path, markdown_path, debt_path) == [
        str(json_path.relative_to(REPO_ROOT).as_posix())
        if json_path.is_relative_to(REPO_ROOT)
        else str(json_path)
    ]


def test_structure_audit_drift_check_detects_markdown_drift(tmp_path: Path) -> None:
    report = _committed_report()
    expected = build_report(REPO_ROOT, generated_at=str(report["generated_at"]))
    json_path = tmp_path / "structure-audit.json"
    markdown_path = tmp_path / "STRUCTURE_AUDIT.md"
    debt_path = tmp_path / "architecture-debt-inventory.json"
    json_path.write_text(render_json_report(expected), encoding="utf-8")
    markdown_path.write_text(render_markdown_report(expected) + "\nextra drift\n", encoding="utf-8")
    debt_path.write_text(render_debt_inventory(expected), encoding="utf-8")

    assert len(detect_report_drift(REPO_ROOT, json_path, markdown_path, debt_path)) == 1


def test_structure_audit_drift_check_detects_debt_inventory_drift(tmp_path: Path) -> None:
    report = _committed_report()
    expected = build_report(REPO_ROOT, generated_at=str(report["generated_at"]))
    json_path = tmp_path / "structure-audit.json"
    markdown_path = tmp_path / "STRUCTURE_AUDIT.md"
    debt_path = tmp_path / "architecture-debt-inventory.json"
    json_path.write_text(render_json_report(expected), encoding="utf-8")
    markdown_path.write_text(render_markdown_report(expected), encoding="utf-8")
    debt_path.write_text(
        render_debt_inventory(
            {
                **expected,
                "debt_inventory": {
                    **expected["debt_inventory"],
                    "untracked_backend_app_python_files": ["backend/app/api/new_feature.py"],
                },
            }
        ),
        encoding="utf-8",
    )

    assert len(detect_report_drift(REPO_ROOT, json_path, markdown_path, debt_path)) == 1


def test_structure_audit_first_generation_is_not_self_stale(tmp_path: Path) -> None:
    json_path = tmp_path / "docs/architecture/structure-audit.json"
    markdown_path = tmp_path / "docs/architecture/STRUCTURE_AUDIT.md"
    debt_path = tmp_path / "docs/architecture/architecture-debt-inventory.json"

    write_report_artifacts(REPO_ROOT, json_path, markdown_path, debt_path)

    assert detect_report_drift(REPO_ROOT, json_path, markdown_path, debt_path) == []


def test_structure_audit_report_has_required_top_level_keys() -> None:
    assert REQUIRED_KEYS.issubset(_committed_report())


def test_structure_audit_reports_frontend_boundary_policy() -> None:
    frontend_boundaries = _committed_report()["frontend_boundaries"]

    assert frontend_boundaries["feature_modules"] == [
        "account-editing",
        "auth",
        "neuro-commenting",
        "warmup",
    ]
    assert frontend_boundaries["shared_module"] == "shared"
    assert frontend_boundaries["module_boundary_test"] is True
    assert frontend_boundaries["missing_indexes"] == []
    assert frontend_boundaries["feature_to_feature_deep_imports"] == []
    assert frontend_boundaries["feature_to_shared_deep_imports"] == []
    assert frontend_boundaries["shared_to_feature_deep_imports"] == []
    assert frontend_boundaries["unexpected_app_deep_module_imports"] == []
    assert frontend_boundaries["unexpected_shared_deep_imports"] == []
    assert frontend_boundaries["allowed_app_deep_module_import_details"] == [
        {
            "key": "../lib/auth.ts -> @/modules/auth/api",
            "source": "../lib/auth.ts",
            "target": "@/modules/auth/api",
            "owner": "auth compatibility wrapper",
            "rationale": "Preserves the legacy @/lib/auth API while auth network implementation lives in the auth module.",
            "removal_condition": "Remove when legacy frontend compatibility wrappers are retired or @/lib/auth no longer re-exports module API internals.",
        },
        {
            "key": "../lib/authBatches.ts -> @/modules/auth/batches",
            "source": "../lib/authBatches.ts",
            "target": "@/modules/auth/batches",
            "owner": "auth compatibility wrapper",
            "rationale": "Preserves the legacy @/lib/authBatches API while bulk-auth implementation lives in the auth module.",
            "removal_condition": "Remove when legacy frontend compatibility wrappers are retired or @/lib/authBatches no longer re-exports module API internals.",
        },
    ]


def test_structure_audit_finding_ids_are_unique_and_sorted() -> None:
    findings = _committed_report()["findings"]
    assert isinstance(findings, list)
    finding_ids = [finding["id"] for finding in findings]
    assert finding_ids == sorted(finding_ids)
    assert len(finding_ids) == len(set(finding_ids))
    assert all(re.fullmatch(r"STRUCTURE-\d{3}", finding_id) for finding_id in finding_ids)


def test_structure_audit_reports_required_unmanaged_domains() -> None:
    entries = _committed_report()["debt_inventory"]["entries"]
    owners = {
        entry["owner"] for entry in entries if entry["category"] == "unmanaged_feature_surface"
    }

    assert "account_lifecycle" not in owners
    assert "account_safety" not in owners
    assert "neuro_commenting" not in owners


def test_structure_audit_phase_three_b_debt_contract_is_exact() -> None:
    report = _committed_report()
    entries = {entry["id"]: entry for entry in report["debt_inventory"]["entries"]}

    assert report["backend_overall_status"] == "YELLOW"
    assert report["debt_inventory"]["summary"]["high_risk_unmanaged_feature_surfaces"] == []
    assert "debt-account-safety" not in entries
    assert "debt-account-lifecycle" not in entries
    assert "debt-neuro-commenting" not in entries
    assert entries["canonical-account-lifecycle"]["status"] == "accepted"
    assert entries["canonical-account-lifecycle"]["severity"] == "info"
    assert entries["canonical-account-profile-completeness"]["status"] == "accepted"
    assert entries["canonical-account-profile-completeness"]["severity"] == "info"


def test_structure_audit_phase_six_c_tracks_all_remaining_legacy_feature_boundaries() -> None:
    report = _committed_report()
    entries = {entry["id"]: entry for entry in report["debt_inventory"]["entries"]}
    unmanaged = [
        entry
        for entry in report["debt_inventory"]["entries"]
        if entry["category"] == "unmanaged_feature_surface"
    ]
    unmanaged_owners = {entry["owner"] for entry in unmanaged}
    residual_legacy = {
        entry["id"]: entry
        for entry in report["debt_inventory"]["entries"]
        if entry["category"] == "residual_legacy_feature_boundary"
    }

    assert "debt-account-legacy-surfaces" not in entries
    assert "account_platform" not in unmanaged_owners
    assert "debt-account-profile-completeness" not in entries
    assert "canonical-account-profile-completeness" in entries
    assert unmanaged == []
    assert set(residual_legacy) == {
        "residual-legacy-account-audit",
        "residual-legacy-account-core",
        "residual-legacy-account-ggr",
        "residual-legacy-account-imports",
        "residual-legacy-account-jobs",
        "residual-legacy-account-profile-state",
        "residual-legacy-account-proxy",
        "residual-legacy-account-quarantine",
        "residual-legacy-account-runtime-status",
        "residual-legacy-account-validity",
        "residual-legacy-bought-onboarding",
        "residual-legacy-human-behavior",
        "residual-legacy-story-surfaces",
    }
    assert all(entry["status"] == "open" for entry in residual_legacy.values())
    assert all(entry["severity"] == "medium" for entry in residual_legacy.values())
    assert all(entry["phase"] == "Phase 6C" for entry in residual_legacy.values())
    assert all(entry["existing_paths"] for entry in residual_legacy.values())
    assert all("follow-up #" in entry["target_owner"] for entry in residual_legacy.values())
    assert (
        "residual_legacy_feature_boundary"
        in report["debt_inventory"]["scope"]["classification_rule"]
    )


def test_structure_audit_phase_six_b_accepts_shared_contracts_storage_boundary() -> None:
    entries = {entry["id"]: entry for entry in _committed_report()["debt_inventory"]["entries"]}
    shared_contracts = entries["shared-contracts-and-orm"]

    assert shared_contracts["category"] == "shared_platform_infrastructure"
    assert shared_contracts["status"] == "accepted"
    assert shared_contracts["severity"] == "medium"
    assert shared_contracts["phase"] == "Phase 6B"
    assert "contracts purity" in shared_contracts["rationale"]
    assert (
        "Promote DTOs to module contracts only when behavior changes"
        in shared_contracts["removal_condition"]
    )


def test_structure_audit_markdown_preserves_live_tdlib_role_flags() -> None:
    report = _committed_report()
    markdown = render_markdown_report(report)
    live_role_names = {
        role["name"] for role in report["runtime_roles"] if role["allows_live_tdlib"]
    }

    assert live_role_names
    for role_name in live_role_names:
        row = next(line for line in markdown.splitlines() if line.startswith(f"| {role_name} |"))
        assert " | Yes | " in row


def test_structure_audit_inventory_entry_ids_are_unique_and_sorted() -> None:
    entries = _committed_report()["debt_inventory"]["entries"]
    entry_ids = [entry["id"] for entry in entries]

    assert entry_ids == sorted(entry_ids)
    assert len(entry_ids) == len(set(entry_ids))


def test_structure_audit_inventory_entries_have_required_metadata() -> None:
    entries = _committed_report()["debt_inventory"]["entries"]
    missing: list[str] = []
    for entry in entries:
        if not entry["paths"]:
            missing.append(f"{entry['id']}: paths")
        if not entry["target_owner"]:
            missing.append(f"{entry['id']}: target_owner")
        if entry["category"] == "unmanaged_feature_surface":
            for key in ("severity", "phase", "removal_condition"):
                if not entry[key] or entry[key] == "n/a":
                    missing.append(f"{entry['id']}: {key}")
            if entry["severity"] == "info":
                missing.append(f"{entry['id']}: severity cannot be info")
        if entry["category"] != "supporting_tool_test_documentation_frontend_evidence":
            if not entry["existing_paths"]:
                missing.append(f"{entry['id']}: existing_paths")

    assert missing == []


def test_residual_boundary_manifest_covers_all_open_residual_entries() -> None:
    report = _committed_report()
    residual_entries = [
        entry
        for entry in report["debt_inventory"]["entries"]
        if entry["category"] == "residual_legacy_feature_boundary"
    ]
    manifest = json.loads(RESIDUAL_MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_by_owner = {entry["owner"]: entry for entry in manifest["entries"]}

    assert report["debt_inventory"]["residual_boundary_guard"]["violations"] == []
    assert sorted(manifest_by_owner) == sorted(entry["owner"] for entry in residual_entries)
    for entry in residual_entries:
        manifest_entry = manifest_by_owner[entry["owner"]]
        assert manifest_entry["entry_id"] == entry["id"]
        assert manifest_entry["related_issue"].startswith("#")
        assert manifest_entry["rationale"]
        assert manifest_entry["removal_condition"]
        assert manifest_entry["verification_scope"]
        assert manifest_entry["existing_paths"] == entry["existing_paths"]
        assert manifest_entry["public_api_fingerprint"]


def test_residual_boundary_guard_blocks_unregistered_file_growth(tmp_path: Path) -> None:
    manifest_path = tmp_path / "docs/architecture/residual-legacy-boundaries.json"
    manifest_path.parent.mkdir(parents=True)
    tracked_path = tmp_path / "backend/app/api/synthetic.py"
    new_path = tmp_path / "backend/app/api/synthetic_extra.py"
    tracked_path.parent.mkdir(parents=True)
    tracked_path.write_text("def existing_surface():\n    return None\n", encoding="utf-8")
    new_path.write_text("def new_surface():\n    return None\n", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "entries": [
                    {
                        "owner": "synthetic",
                        "entry_id": "residual-legacy-synthetic",
                        "related_issue": "#999",
                        "rationale": "Synthetic residual boundary.",
                        "removal_condition": "Migrate synthetic boundary.",
                        "verification_scope": "Synthetic verification.",
                        "paths": ["backend/app/api/synthetic.py"],
                        "existing_paths": ["backend/app/api/synthetic.py"],
                        "public_api_fingerprint": [
                            "backend/app/api/synthetic.py:function:existing_surface"
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    entries = [
        {
            "id": "residual-legacy-synthetic",
            "category": "residual_legacy_feature_boundary",
            "owner": "synthetic",
            "existing_paths": [
                "backend/app/api/synthetic.py",
                "backend/app/api/synthetic_extra.py",
            ],
        }
    ]

    guard = _residual_boundary_guard(tmp_path, entries)

    assert (
        "synthetic: new residual path backend/app/api/synthetic_extra.py is not in manifest"
        in guard["violations"]
    )


def test_residual_boundary_guard_blocks_public_surface_growth(tmp_path: Path) -> None:
    manifest_path = tmp_path / "docs/architecture/residual-legacy-boundaries.json"
    manifest_path.parent.mkdir(parents=True)
    tracked_path = tmp_path / "backend/app/api/synthetic.py"
    tracked_path.parent.mkdir(parents=True)
    tracked_path.write_text(
        "def existing_surface():\n    return None\n\ndef new_surface():\n    return None\n",
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "entries": [
                    {
                        "owner": "synthetic",
                        "entry_id": "residual-legacy-synthetic",
                        "related_issue": "#999",
                        "rationale": "Synthetic residual boundary.",
                        "removal_condition": "Migrate synthetic boundary.",
                        "verification_scope": "Synthetic verification.",
                        "paths": ["backend/app/api/synthetic.py"],
                        "existing_paths": ["backend/app/api/synthetic.py"],
                        "public_api_fingerprint": [
                            "backend/app/api/synthetic.py:function:existing_surface"
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    entries = [
        {
            "id": "residual-legacy-synthetic",
            "category": "residual_legacy_feature_boundary",
            "owner": "synthetic",
            "existing_paths": ["backend/app/api/synthetic.py"],
        }
    ]

    guard = _residual_boundary_guard(tmp_path, entries)

    assert (
        "synthetic: new public surface backend/app/api/synthetic.py:function:new_surface is not in manifest"
        in guard["violations"]
    )


def test_backend_overall_yellow_while_residual_boundaries_remain() -> None:
    report = _committed_report()
    rendered_json = json.loads(render_json_report(report))

    assert rendered_json["backend_overall_status"] == "YELLOW"
    assert rendered_json["debt_inventory"]["summary"]["open_count"] == 13
    assert rendered_json["debt_inventory"]["summary"]["unmanaged_feature_surface_count"] == 0
    assert (
        rendered_json["debt_inventory"]["summary"]["residual_legacy_feature_boundary_count"] == 13
    )
    assert report["debt_inventory"]["summary"]["high_risk_unmanaged_feature_surface_count"] == 0
    assert (
        rendered_json["debt_inventory"]["summary"]["high_risk_unmanaged_feature_surface_count"] == 0
    )
    assert report["backend_overall_status"] == "YELLOW"


def test_phase_six_c_residual_findings_remain_open() -> None:
    report = _committed_report()
    findings = {finding["id"]: finding for finding in report["findings"]}

    assert findings["STRUCTURE-001"]["severity"] == "medium"
    assert findings["STRUCTURE-001"]["status"] == "open"
    assert "residual legacy feature boundaries" in findings["STRUCTURE-001"]["finding"]
    assert "high-risk feature ownership" not in findings["STRUCTURE-001"]["finding"]
    assert findings["STRUCTURE-002"]["severity"] == "info"
    assert findings["STRUCTURE-002"]["status"] == "accepted"
    assert findings["STRUCTURE-008"]["severity"] == "medium"
    assert findings["STRUCTURE-008"]["status"] == "open"


def test_phase_six_c_markdown_is_truthful_yellow() -> None:
    markdown = render_markdown_report(_committed_report())

    assert (
        "| Backend overall | YELLOW | 13 residual legacy feature boundaries remain outside app.modules."
        in markdown
    )
    assert "| Unmanaged feature debt | GREEN | No unmanaged feature debt." in markdown
    assert "| Residual legacy feature boundaries | YELLOW |" in markdown
    assert "| Frontend ownership | GREEN |" in markdown
    assert "| STRUCTURE-001 | medium | open |" in markdown
    assert "| STRUCTURE-002 | info | accepted |" in markdown
    assert "high-risk feature ownership" not in markdown


def test_structure_audit_synthetic_high_risk_debt_is_reported_truthfully() -> None:
    report = _report_with_unmanaged_entries(
        build_report(REPO_ROOT, generated_at="2026-05-26T10:11:12Z"),
        [_unmanaged_entry(entry_id="debt-synthetic-high", owner="synthetic_high", severity="high")],
    )
    findings = {finding["id"]: finding for finding in report["findings"]}
    markdown = render_markdown_report(report)
    rendered_json = json.loads(render_json_report(report))

    assert report["backend_overall_status"] == "RED"
    assert rendered_json["debt_inventory"]["summary"]["high_risk_unmanaged_feature_surfaces"] == [
        "debt-synthetic-high"
    ]
    assert findings["STRUCTURE-001"]["severity"] == "high"
    assert "high-risk feature ownership" in findings["STRUCTURE-001"]["finding"]
    assert "high-risk unmanaged feature surfaces" in findings["STRUCTURE-001"]["recommendation"]
    assert "debt-synthetic-high" in findings["STRUCTURE-001"]["evidence"]
    assert findings["STRUCTURE-008"]["severity"] == "high"
    assert (
        "| Backend overall | RED | 1 high-risk and 0 medium unmanaged feature surfaces remain."
        in markdown
    )
    assert "| Unmanaged feature debt | RED | synthetic_high |" in markdown
    assert "debt-synthetic-high" in markdown
    assert "Keep medium debt visible" not in markdown


def test_structure_audit_synthetic_all_residual_boundaries_migrated_permits_green() -> None:
    report = _report_with_open_debt_entries(
        build_report(REPO_ROOT, generated_at="2026-05-26T10:11:12Z"),
    )
    findings = {finding["id"]: finding for finding in report["findings"]}
    markdown = render_markdown_report(report)
    rendered_json = json.loads(render_json_report(report))

    assert report["backend_overall_status"] == "GREEN"
    assert rendered_json["debt_inventory"]["summary"]["unmanaged_feature_surface_count"] == 0
    assert rendered_json["debt_inventory"]["summary"]["residual_legacy_feature_boundary_count"] == 0
    assert findings["STRUCTURE-001"]["status"] == "accepted"
    assert findings["STRUCTURE-001"]["severity"] == "info"
    assert "no unmanaged feature debt is open" in findings["STRUCTURE-001"]["evidence"]
    assert findings["STRUCTURE-008"]["status"] == "accepted"
    assert findings["STRUCTURE-008"]["severity"] == "info"
    assert "No unmanaged feature debt remains." in markdown
    assert "unmanaged feature surfaces remain" not in markdown
    backend_modules_row = next(
        line for line in markdown.splitlines() if line.startswith("| Backend modules |")
    )
    unmanaged_debt_row = next(
        line for line in markdown.splitlines() if line.startswith("| Unmanaged feature debt |")
    )
    assert "account platform debt split" not in backend_modules_row
    assert "New feature behavior can bypass app.modules" not in unmanaged_debt_row


def test_structure_audit_synthetic_residual_boundary_is_reported_truthfully() -> None:
    report = _report_with_open_debt_entries(
        build_report(REPO_ROOT, generated_at="2026-05-26T10:11:12Z"),
        residual_entries=[
            _residual_entry(entry_id="residual-legacy-synthetic", owner="synthetic_residual")
        ],
    )
    findings = {finding["id"]: finding for finding in report["findings"]}
    markdown = render_markdown_report(report)
    rendered_json = json.loads(render_json_report(report))

    assert report["backend_overall_status"] == "YELLOW"
    assert rendered_json["debt_inventory"]["summary"]["residual_legacy_feature_boundaries"] == [
        "residual-legacy-synthetic"
    ]
    assert findings["STRUCTURE-001"]["severity"] == "medium"
    assert findings["STRUCTURE-001"]["status"] == "open"
    assert "synthetic" in findings["STRUCTURE-001"]["evidence"]
    assert findings["STRUCTURE-008"]["severity"] == "medium"
    assert "| Residual legacy feature boundaries | YELLOW | synthetic_residual |" in markdown


def test_backend_app_python_files_are_classified_by_inventory() -> None:
    untracked = _committed_report()["debt_inventory"]["untracked_backend_app_python_files"]

    assert untracked == []


def test_backend_app_python_files_are_classified_once_by_inventory() -> None:
    overlaps = _committed_report()["debt_inventory"]["overlapping_backend_app_python_files"]

    assert overlaps == {}


def test_structure_audit_untracked_backend_app_files_block_green_closure() -> None:
    report = build_report(REPO_ROOT, generated_at="2026-05-26T10:11:12Z")
    report["debt_inventory"]["untracked_backend_app_python_files"] = [
        "backend/app/api/new_feature.py"
    ]
    report["backend_overall_status"] = _backend_overall_status(report["debt_inventory"])
    report["findings"] = _findings(
        report["boundaries"],
        report["forbidden_runtime_claims"],
        report["debt_inventory"],
        report["frontend_boundaries"],
    )
    findings = {finding["id"]: finding for finding in report["findings"]}
    markdown = render_markdown_report(report)

    assert report["backend_overall_status"] == "RED"
    assert findings["STRUCTURE-001"]["severity"] == "high"
    assert findings["STRUCTURE-008"]["severity"] == "high"
    assert "backend/app/api/new_feature.py" in findings["STRUCTURE-008"]["evidence"]
    assert "| Untracked backend/app production files | RED |" in markdown


def test_module_template_is_reported_but_not_registered() -> None:
    modules = _committed_report()["modules"]
    template = next(module for module in modules if module["name"] == "_template")
    assert template["documentation_only"] is True
    assert template["registered"] is False
    assert template["template_files_are_non_runtime"] is True


def test_audit_report_does_not_claim_broadcast_or_analytics_runtime() -> None:
    report = _committed_report()
    assert report["forbidden_runtime_claims"] == {"queues": [], "workflows": []}
    runtime_names = {role["name"] for role in report["runtime_roles"]}
    queue_names = {queue["name"] for queue in report["queues"]}
    workflow_types = {workflow["workflow_type"] for workflow in report["workflows"]}
    for forbidden in ("broadcast", "analytics"):
        assert all(forbidden not in name for name in runtime_names)
        assert all(forbidden not in name for name in queue_names)
        assert all(forbidden not in workflow_type for workflow_type in workflow_types)


def test_structure_audit_report_includes_split_reserved_runtime_roles() -> None:
    roles = {
        role["name"]: role["queues"]
        for role in _committed_report()["runtime_roles"]
        if role["name"]
        in {
            "maintenance_worker",
            "media_worker",
            "story_worker",
            "account_lifecycle_worker",
        }
    }

    assert roles == {
        "maintenance_worker": ["maintenance_jobs"],
        "media_worker": ["media_jobs"],
        "story_worker": ["story_jobs"],
        "account_lifecycle_worker": ["account_lifecycle_jobs"],
    }


def test_structure_005_no_longer_reports_broad_maintenance_ownership() -> None:
    findings = {finding["id"]: finding for finding in _committed_report()["findings"]}
    finding = findings["STRUCTURE-005"]

    assert finding["status"] == "accepted"
    assert "temporarily owns reserved" not in finding["finding"]
    assert "logically split" in finding["finding"]
    assert "staging may still group queues" in finding["risk"]


def test_structure_audit_report_preserves_workflow_args_modes() -> None:
    workflows = {
        workflow["workflow_type"]: workflow["args_mode"]
        for workflow in _committed_report()["workflows"]
    }
    assert workflows["account_update"] == "JOB_ID"
    assert workflows["warmup_due_sessions"] == "NONE"
    assert workflows["warmup_dispatch_tick"] == "NONE"
