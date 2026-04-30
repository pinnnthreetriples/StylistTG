from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.storage.errors import InvalidStorageKeyError


_SAFE_ACCOUNT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def normalize_storage_key(key: str | Path) -> str:
    raw = str(key).replace("\\", "/").strip()
    if not raw:
        raise InvalidStorageKeyError("storage key is empty")
    if raw.startswith("/") or raw.startswith("~"):
        raise InvalidStorageKeyError("absolute storage keys are not allowed")
    if re.match(r"^[A-Za-z]:($|/)", raw):
        raise InvalidStorageKeyError("drive-letter storage keys are not allowed")

    parts: list[str] = []
    for part in raw.split("/"):
        if not part:
            continue
        if part == ".":
            raise InvalidStorageKeyError("period-only storage key segments are not allowed")
        if part == "..":
            raise InvalidStorageKeyError("storage key traversal is not allowed")
        parts.append(part)
    if not parts:
        raise InvalidStorageKeyError("storage key is empty")
    return "/".join(parts)


def asset_source_key(asset_id: str, filename: str) -> str:
    return normalize_storage_key(f"assets/{asset_id}/source/{filename}")


def asset_normalized_key(asset_id: str, filename: str) -> str:
    return normalize_storage_key(f"assets/{asset_id}/normalized/{filename}")


def asset_prefix(asset_id: str) -> str:
    return normalize_storage_key(f"assets/{asset_id}")


def validate_tdlib_account_id(account_id: str) -> str:
    if not _SAFE_ACCOUNT_ID_RE.fullmatch(account_id):
        raise InvalidStorageKeyError("unsafe TDLib account id")
    if "." in account_id or "/" in account_id or "\\" in account_id:
        raise InvalidStorageKeyError("unsafe TDLib account id")
    return account_id


def resolve_child_path(root: Path, *parts: str, create: bool = False) -> Path:
    root_resolved = root.resolve()
    candidate = root_resolved.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise InvalidStorageKeyError("path escapes configured storage root") from exc
    if create:
        candidate.mkdir(parents=True, exist_ok=True)
    return candidate


@dataclass(frozen=True)
class TdlibAccountStorageDirs:
    database_directory: Path
    files_directory: Path


def resolve_tdlib_account_dirs(
    config: Settings,
    account_id: str,
    *,
    create: bool = True,
) -> TdlibAccountStorageDirs:
    safe_account_id = validate_tdlib_account_id(account_id)
    database_directory = resolve_child_path(
        config.tdlib_database_root,
        safe_account_id,
        create=create,
    )
    files_directory = resolve_child_path(
        config.tdlib_files_root,
        safe_account_id,
        create=create,
    )
    return TdlibAccountStorageDirs(
        database_directory=database_directory,
        files_directory=files_directory,
    )
