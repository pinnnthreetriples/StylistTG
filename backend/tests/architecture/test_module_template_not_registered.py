from __future__ import annotations

from pathlib import Path

from app.modules.registry import iter_modules, iter_workflows


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_template_module_is_not_registered() -> None:
    module_names = {module.name for module in iter_modules()}

    assert "_template" not in module_names


def test_registry_does_not_import_template_package() -> None:
    registry_source = (BACKEND_ROOT / "app" / "modules" / "registry.py").read_text(encoding="utf-8")

    assert "app.modules." + "_template" not in registry_source


def test_future_modules_have_no_workflow_types() -> None:
    workflow_types = {workflow.workflow_type for workflow in iter_workflows()}

    assert not any("broadcast" in workflow_type for workflow_type in workflow_types)
    assert not any("analytics" in workflow_type for workflow_type in workflow_types)


def test_future_modules_have_no_queue_names() -> None:
    future_queue_names = ("broadcast" + "_jobs", "analytics" + "_jobs")
    for path in (BACKEND_ROOT / "app").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for queue_name in future_queue_names:
            assert queue_name not in source
