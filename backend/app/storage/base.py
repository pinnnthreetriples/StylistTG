from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class StorageObject:
    key: str
    path: Path | None
    uri: str
    size_bytes: int
    content_type: str | None
    checksum: str | None
    storage_backend: str
    visibility: str
    created_at: datetime | None = None


class StorageService(Protocol):
    backend_name: str

    def save_bytes(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str | None = None,
        visibility: str = "private",
    ) -> StorageObject: ...

    def save_file(
        self,
        key: str,
        source_path: Path,
        *,
        content_type: str | None = None,
        visibility: str = "private",
    ) -> StorageObject: ...

    def open_read(self, key: str) -> BinaryIO: ...

    def read_bytes(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> bool: ...

    def get_uri(self, key: str) -> str: ...

    def get_signed_url(self, key: str, *, expires_seconds: int = 300) -> str: ...

    def copy(self, source_key: str, destination_key: str) -> StorageObject: ...

    def stat(self, key: str) -> StorageObject: ...

    def cleanup_prefix(
        self,
        prefix: str,
        *,
        dry_run: bool = True,
        max_delete_count: int = 100,
    ) -> list[str]: ...
