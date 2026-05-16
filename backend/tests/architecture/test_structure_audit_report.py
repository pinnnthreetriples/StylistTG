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

from structure_audit import build_report  # noqa: E402


REPORT_PATH = REPO_ROOT / "docs/architecture/structure-audit.json"
REQUIRED_KEYS = {
    "generated_at",
    "modules",
    "runtime_roles",
    "queues",
    "legacy_wrappers",
    "architecture_tests",
    "frontend_modules",
    "security_checks",
    "findings",
}


def _committed_report() -> dict[str, object]:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_structure_audit_report_matches_static_script() -> None:
    assert _committed_report() == build_report(REPO_ROOT)


def test_structure_audit_report_has_required_top_level_keys() -> None:
    assert REQUIRED_KEYS.issubset(_committed_report())


def test_structure_audit_finding_ids_are_unique_and_sorted() -> None:
    findings = _committed_report()["findings"]
    assert isinstance(findings, list)
    finding_ids = [finding["id"] for finding in findings]
    assert finding_ids == sorted(finding_ids)
    assert len(finding_ids) == len(set(finding_ids))
    assert all(re.fullmatch(r"STRUCTURE-\d{3}", finding_id) for finding_id in finding_ids)


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
