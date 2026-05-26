from __future__ import annotations

import ast
from pathlib import Path

from app.contracts.queues import PRODUCTION_QUEUE_NAMES
from app.runtime.roles import iter_runtime_roles


BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"


def _imports_for(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_runtime_package_does_not_import_api_or_fastapi_layers() -> None:
    for path in (APP_ROOT / "runtime").glob("*.py"):
        imports = _imports_for(path)
        assert "fastapi" not in imports
        assert not any(name == "app.api" or name.startswith("app.api.") for name in imports)


def test_runtime_preflight_does_not_import_tdlib_or_worker_modules() -> None:
    imports = _imports_for(APP_ROOT / "runtime" / "preflight.py")

    assert not any("tdlib" in name for name in imports)
    assert not any(name == "app.workers" or name.startswith("app.workers.") for name in imports)


def test_runtime_roles_use_existing_queue_constants() -> None:
    allowed = set(PRODUCTION_QUEUE_NAMES)

    assert {queue for role in iter_runtime_roles() for queue in role.queues} <= allowed
    assert "app.contracts.queues" in _imports_for(APP_ROOT / "runtime" / "roles.py")


def test_reserved_runtime_roles_are_split() -> None:
    roles = {role.name: role.queues for role in iter_runtime_roles()}

    assert roles["maintenance_worker"] == ("maintenance_jobs",)
    assert roles["media_worker"] == ("media_jobs",)
    assert roles["story_worker"] == ("story_jobs",)
    assert roles["account_lifecycle_worker"] == ("account_lifecycle_jobs",)
