from __future__ import annotations

from pathlib import Path

from app.config import Settings, settings
from app.models import Asset
from app.storage import LocalStorageService, StorageService, build_storage_service
from app.storage.errors import InvalidStorageKeyError
from app.storage.paths import normalize_storage_key


def asset_source_storage_key(asset: Asset) -> str:
    return normalize_storage_key(asset.source_key or asset.source_path)


def asset_normalized_storage_key(asset: Asset) -> str:
    return normalize_storage_key(asset.normalized_key or asset.normalized_path)


def build_asset_storage(config: Settings = settings) -> StorageService:
    return build_storage_service(config)


def materialize_asset_to_local_path(
    asset: Asset,
    *,
    config: Settings = settings,
    storage: StorageService | None = None,
) -> Path:
    storage_service = storage or build_asset_storage(config)
    key = asset_normalized_storage_key(asset)
    if isinstance(storage_service, LocalStorageService):
        return storage_service.resolve_path(key)

    local_cache = LocalStorageService(config.storage_root)
    cache_key = normalize_storage_key(f"execution-cache/{asset.id}/{Path(key).name}")
    local_path = local_cache.resolve_path(cache_key)
    if not local_path.exists():
        content = storage_service.read_bytes(key)
        local_cache.save_bytes(cache_key, content, content_type=asset.normalized_content_type or asset.mime)
    return local_path


def get_asset_signed_url(
    asset: Asset,
    *,
    config: Settings = settings,
    storage: StorageService | None = None,
) -> str:
    storage_service = storage or build_asset_storage(config)
    key = asset_normalized_storage_key(asset)
    if not key.startswith("assets/"):
        raise InvalidStorageKeyError("signed URLs are only available for application assets")
    return storage_service.get_signed_url(
        key,
        expires_seconds=config.storage_s3_signed_url_expires_seconds,
    )
