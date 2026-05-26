from __future__ import annotations

import json
import re
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
SCRIPTS_ROOT = BACKEND_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from structure_audit import (  # noqa: E402
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
    "debt_inventory",
    "security_checks",
    "findings",
}


def _committed_report() -> dict[str, object]:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


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
        render_json_report({**expected, "backend_overall_status": "GREEN"}), encoding="utf-8"
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

    assert {"neuro_commenting", "account_safety", "account_lifecycle"}.issubset(owners)


def test_structure_audit_phase_zero_debt_contract_is_exact() -> None:
    report = _committed_report()
    entries = {entry["id"]: entry for entry in report["debt_inventory"]["entries"]}

    assert report["backend_overall_status"] == "RED"
    assert report["debt_inventory"]["summary"]["high_risk_unmanaged_feature_surfaces"] == [
        "debt-account-safety",
        "debt-neuro-commenting",
    ]
    assert entries["debt-account-safety"]["status"] == "open"
    assert entries["debt-account-safety"]["severity"] == "high"
    assert entries["debt-neuro-commenting"]["status"] == "open"
    assert entries["debt-neuro-commenting"]["severity"] == "high"
    assert entries["debt-account-lifecycle"]["status"] == "open"
    assert entries["debt-account-lifecycle"]["severity"] == "medium"


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


def test_backend_overall_not_green_with_high_risk_unmanaged_surfaces() -> None:
    report = _committed_report()

    assert report["debt_inventory"]["summary"]["high_risk_unmanaged_feature_surface_count"] > 0
    assert report["backend_overall_status"] != "GREEN"


def test_backend_app_python_files_are_classified_by_inventory() -> None:
    untracked = _committed_report()["debt_inventory"]["untracked_backend_app_python_files"]

    assert untracked == []


def test_backend_app_python_files_are_classified_once_by_inventory() -> None:
    overlaps = _committed_report()["debt_inventory"]["overlapping_backend_app_python_files"]

    assert overlaps == {}


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
