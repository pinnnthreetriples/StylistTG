from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset
from app.storage import LocalStorageService, StorageService
from app.storage.errors import InvalidStorageKeyError
from app.storage.paths import normalize_storage_key


@dataclass
class AssetCleanupReport:
    scanned: int = 0
    deleted: list[str] = field(default_factory=lambda: [])
    skipped: list[str] = field(default_factory=lambda: [])
    errors: list[str] = field(default_factory=lambda: [])


def cleanup_orphan_asset_directories(
    session: Session,
    storage: StorageService,
    *,
    dry_run: bool = True,
    max_delete_count: int = 100,
) -> AssetCleanupReport:
    report = AssetCleanupReport()
    if not isinstance(storage, LocalStorageService):
        report.skipped.append("non-local storage cleanup is not implemented")
        return report

    assets_root = storage.resolve_path("assets")
    if not assets_root.exists():
        return report

    known_asset_ids: set[str] = set(session.execute(select(Asset.id)).scalars().all())
    delete_count = 0
    for child in assets_root.iterdir():
        report.scanned += 1
        if not child.is_dir():
            report.skipped.append(storage_key(storage, child))
            continue
        asset_id = child.name
        if asset_id in known_asset_ids:
            report.skipped.append(storage_key(storage, child))
            continue
        try:
            prefix = normalize_storage_key(f"assets/{asset_id}")
        except InvalidStorageKeyError as exc:
            report.errors.append(f"{child.name}: {exc}")
            continue
        delete_count += 1
        if delete_count > max_delete_count:
            report.errors.append("max delete count exceeded")
            break
        if not dry_run:
            storage.delete(prefix)
        report.deleted.append(prefix)
    return report


def storage_key(storage: LocalStorageService, path: Path) -> str:
    return path.resolve().relative_to(storage.root.resolve()).as_posix()
