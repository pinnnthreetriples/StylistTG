from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
SCRIPTS_ROOT = BACKEND_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from legacy_wrapper_audit import VALID_STAGES, build_manifest, validate_manifest  # noqa: E402


MANIFEST_PATH = REPO_ROOT / "docs/architecture/legacy-wrappers.json"


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_legacy_wrapper_manifest_is_valid_json() -> None:
    manifest = _manifest()

    assert manifest["generated_at"] == "2026-05-17T00:00:00Z"
    assert isinstance(manifest["wrappers"], list)


def test_legacy_wrapper_manifest_matches_script_output() -> None:
    assert _manifest() == build_manifest()


def test_legacy_wrapper_manifest_entries_are_sorted_and_use_valid_stages() -> None:
    wrappers = _manifest()["wrappers"]
    legacy_paths = [wrapper["legacy_path"] for wrapper in wrappers]

    assert legacy_paths == sorted(legacy_paths)
    assert all(wrapper["stage"] in VALID_STAGES for wrapper in wrappers)


def test_legacy_wrapper_manifest_files_have_compatibility_markers() -> None:
    errors = validate_manifest(REPO_ROOT, _manifest())

    assert errors == []


def test_legacy_wrapper_manifest_rejects_invalid_stage() -> None:
    manifest = build_manifest()
    manifest["wrappers"][0]["stage"] = "stage_9_invalid"

    errors = validate_manifest(REPO_ROOT, manifest)

    assert "docs/architecture/legacy-wrappers.json does not match generated manifest" in errors
    assert any("uses invalid stage 'stage_9_invalid'" in error for error in errors)
