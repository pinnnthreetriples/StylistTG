from __future__ import annotations

import ast
from pathlib import Path

from app.contracts.queues import (
    PROFILE_QUEUE_NAME,
    WARMUP_DISPATCH_QUEUE_NAME,
    WARMUP_QUEUE_NAME,
)
from app.modules.registry import get_workflow_spec


RQ_MODULE = Path("app/job_queue/rq.py")
BACKEND_ROOTS = (Path("app"), Path("tests"))
FORBIDDEN_RQ_IMPORTS = (
    "app.workers.account_update_jobs",
    "app.workers.warmup_jobs",
    "app.workers.warmup_dispatch_jobs",
    "app.services.account_update_jobs",
    "app.services.account_update_plan",
    "app.services.warmup",
    "app.services.warmup_worker",
    "app.services.warmup_dispatch",
)


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _python_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def _workflow_assignment_literal(name: str, quote: str) -> str:
    return f"workflow_type={quote}{name}{quote}"


def test_rq_does_not_import_legacy_feature_workers_or_services() -> None:
    violations = [
        imported
        for imported in _imports(RQ_MODULE)
        if any(imported == forbidden for forbidden in FORBIDDEN_RQ_IMPORTS)
    ]

    assert violations == []


def test_workflow_metadata_keeps_stable_handler_paths_and_queues() -> None:
    account_update = get_workflow_spec("account_update")
    warmup_due = get_workflow_spec("warmup_due_sessions")
    warmup_dispatch = get_workflow_spec("warmup_dispatch_tick")

    assert account_update.queue_name == PROFILE_QUEUE_NAME
    assert account_update.handler_path == "app.modules.account_editing.jobs:run_account_update_job"
    assert warmup_due.queue_name == WARMUP_QUEUE_NAME
    assert warmup_due.handler_path == "app.modules.warmup.jobs:run_warmup_due_sessions"
    assert warmup_dispatch.queue_name == WARMUP_DISPATCH_QUEUE_NAME
    assert warmup_dispatch.handler_path == "app.modules.warmup.jobs:run_warmup_dispatch_tick"


def test_forbidden_feature_workflow_types_are_not_introduced() -> None:
    violations: list[str] = []
    for root in BACKEND_ROOTS:
        for source in _python_files(root):
            if source == Path("tests/architecture/test_job_queue_boundaries.py"):
                continue
            text = source.read_text(encoding="utf-8")
            if _workflow_assignment_literal("account_editing", '"') in text or (
                _workflow_assignment_literal("account_editing", "'") in text
            ):
                violations.append(str(source))
            if _workflow_assignment_literal("warmup", '"') in text or (
                _workflow_assignment_literal("warmup", "'") in text
            ):
                violations.append(str(source))

    assert violations == []
