from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from app.storage.base import StorageObject
from app.storage.errors import StorageConfigurationError


class S3CompatibleStorageService:
    backend_name = "s3"

    def __init__(
        self,
        *,
        endpoint_url: str,
        bucket: str,
        region: str | None,
        access_key_id: str,
        secret_access_key: str,
        force_path_style: bool,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.bucket = bucket
        self.region = region
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.force_path_style = force_path_style

    def _not_ready(self) -> StorageConfigurationError:
        return StorageConfigurationError(
            "S3-compatible storage is configured but the object-storage client "
            "is not wired in this foundation slice."
        )

    def save_bytes(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str | None = None,
        visibility: str = "private",
    ) -> StorageObject:
        raise self._not_ready()

    def save_file(
        self,
        key: str,
        source_path: Path,
        *,
        content_type: str | None = None,
        visibility: str = "private",
    ) -> StorageObject:
        raise self._not_ready()

    def open_read(self, key: str) -> BinaryIO:
        raise self._not_ready()

    def exists(self, key: str) -> bool:
        raise self._not_ready()

    def delete(self, key: str) -> bool:
        raise self._not_ready()

    def get_uri(self, key: str) -> str:
        raise self._not_ready()

    def get_signed_url(self, key: str, *, expires_seconds: int = 300) -> str:
        raise self._not_ready()

    def copy(self, source_key: str, destination_key: str) -> StorageObject:
        raise self._not_ready()

    def stat(self, key: str) -> StorageObject:
        raise self._not_ready()

    def cleanup_prefix(
        self,
        prefix: str,
        *,
        dry_run: bool = True,
        max_delete_count: int = 100,
    ) -> list[str]:
        raise self._not_ready()
