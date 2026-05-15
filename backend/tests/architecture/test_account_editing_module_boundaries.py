from __future__ import annotations

import ast
from pathlib import Path


ACCOUNT_EDITING_ROOT = Path("app/modules/account_editing")
ACCOUNT_EDITING_INIT = ACCOUNT_EDITING_ROOT / "__init__.py"
ACCOUNT_EDITING_CONTRACTS = ACCOUNT_EDITING_ROOT / "contracts.py"
ACCOUNT_EDITING_ROUTER = ACCOUNT_EDITING_ROOT / "router.py"
MOVED_DTO_NAMES = (
    "AccountUpdateCreate",
    "AccountUpdateJobSummaryRead",
    "AccountUpdatePreviewRead",
    "AccountUpdateProfileAudioDesiredState",
    "AccountUpdateProfileDesiredState",
    "AccountUpdateStoryDesiredState",
)
FORBIDDEN_CONTRACT_IMPORTS = (
    "app.models",
    "sqlalchemy",
    "fastapi",
    "redis",
    "rq",
    "app.adapters.tdlib",
    "app.adapters.tdlib_profile_execution",
)


def _imports(path: Path) -> list[tuple[str, tuple[str, ...]]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[str, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, ()) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.module, tuple(alias.name for alias in node.names)))
    return imports


def _has_import(imported: str, forbidden: str) -> bool:
    return imported == forbidden or imported.startswith(f"{forbidden}.")


def test_account_editing_contracts_exist_and_are_public() -> None:
    init_source = ACCOUNT_EDITING_INIT.read_text(encoding="utf-8")

    assert ACCOUNT_EDITING_CONTRACTS.exists()
    assert (ACCOUNT_EDITING_ROOT / "enqueue.py").exists()
    assert '"contracts"' in init_source
    assert '"enqueue"' in init_source


def test_account_editing_contracts_do_not_import_runtime_or_persistence() -> None:
    violations = [
        imported
        for imported, _names in _imports(ACCOUNT_EDITING_CONTRACTS)
        if any(_has_import(imported, forbidden) for forbidden in FORBIDDEN_CONTRACT_IMPORTS)
    ]

    assert violations == []


def test_account_editing_router_uses_module_contracts_for_moved_dtos() -> None:
    imports = _imports(ACCOUNT_EDITING_ROUTER)

    assert ("app.modules.account_editing.contracts", MOVED_DTO_NAMES[:3]) in imports
    assert not any(
        imported == "app.schemas" and set(names) & set(MOVED_DTO_NAMES)
        for imported, names in imports
    )


def test_app_schemas_reexports_moved_account_editing_contracts() -> None:
    from app import schemas
    from app.modules.account_editing import contracts

    assert schemas.AccountUpdateCreate is contracts.AccountUpdateCreate
    assert schemas.AccountUpdatePreviewRead is contracts.AccountUpdatePreviewRead
    assert schemas.AccountUpdateJobSummaryRead is contracts.AccountUpdateJobSummaryRead
