from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings, settings

SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


@dataclass(frozen=True)
class TdlibStoragePaths:
    storage_key: str
    database_path: Path
    files_path: Path

    def public_summary(self) -> dict[str, bool | str]:
        return {"storage_key": self.storage_key, "database_path_configured": True, "files_path_configured": True}


def build_account_tdlib_paths(
    *,
    workspace_id: str,
    account_id: str,
    config: Settings = settings,
) -> TdlibStoragePaths:
    return _build_paths(workspace_id=workspace_id, leaf=account_id, config=config)


def build_auth_session_tdlib_paths(
    *,
    workspace_id: str,
    auth_session_id: str,
    config: Settings = settings,
) -> TdlibStoragePaths:
    return _build_paths(workspace_id=workspace_id, leaf=f"auth-sessions/{_safe_segment(auth_session_id)}", config=config)


def _build_paths(*, workspace_id: str, leaf: str, config: Settings) -> TdlibStoragePaths:
    workspace = _safe_segment(workspace_id)
    leaf_parts = [_safe_segment(part) for part in leaf.split("/")]
    storage_key = "/".join([workspace, *leaf_parts])
    database_path = _safe_join(config.tdlib_database_root, workspace, *leaf_parts)
    files_path = _safe_join(config.tdlib_files_root, workspace, *leaf_parts)
    return TdlibStoragePaths(storage_key=storage_key, database_path=database_path, files_path=files_path)


def _safe_segment(value: str) -> str:
    if not SAFE_SEGMENT_RE.fullmatch(value):
        raise ValueError("TDLib storage segment contains unsafe characters")
    if value in {".", ".."}:
        raise ValueError("TDLib storage segment cannot be a relative path marker")
    return value


def _safe_join(root: Path, *parts: str) -> Path:
    root_resolved = Path(root).resolve()
    candidate = root_resolved.joinpath(*parts).resolve()
    if root_resolved != candidate and root_resolved not in candidate.parents:
        raise ValueError("TDLib storage path escapes configured root")
    return candidate
