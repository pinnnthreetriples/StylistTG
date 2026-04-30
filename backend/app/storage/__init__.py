from __future__ import annotations

from app.config import Settings, settings
from app.storage.base import StorageObject, StorageService
from app.storage.local import LocalStorageService
from app.storage.s3_compatible import S3CompatibleStorageService


def build_storage_service(config: Settings = settings) -> StorageService:
    if config.storage_backend == "local":
        return LocalStorageService(config.storage_root, public_base_url=config.storage_public_base_url)
    if config.storage_backend == "s3":
        return S3CompatibleStorageService(
            endpoint_url=config.storage_s3_endpoint_url or "",
            bucket=config.storage_s3_bucket or "",
            region=config.storage_s3_region,
            access_key_id=config.storage_s3_access_key_id or "",
            secret_access_key=(
                config.storage_s3_secret_access_key.get_secret_value()
                if config.storage_s3_secret_access_key
                else ""
            ),
            force_path_style=config.storage_s3_force_path_style,
            public_base_url=config.storage_s3_public_base_url,
        )
    raise ValueError(f"unsupported storage backend: {config.storage_backend}")


__all__ = ["StorageObject", "StorageService", "LocalStorageService", "build_storage_service"]
