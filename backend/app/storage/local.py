from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from app.storage.base import StorageObject
from app.storage.errors import InvalidStorageKeyError, StorageObjectNotFoundError
from app.storage.paths import normalize_storage_key


class LocalStorageService:
    backend_name = "local"

    def __init__(self, root: Path, *, public_base_url: str | None = None) -> None:
        self.root = root
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None

    def save_bytes(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str | None = None,
        visibility: str = "private",
    ) -> StorageObject:
        normalized_key = normalize_storage_key(key)
        path = self.resolve_path(normalized_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return self.stat(normalized_key, content_type=content_type, visibility=visibility)

    def save_file(
        self,
        key: str,
        source_path: Path,
        *,
        content_type: str | None = None,
        visibility: str = "private",
    ) -> StorageObject:
        normalized_key = normalize_storage_key(key)
        path = self.resolve_path(normalized_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, path)
        return self.stat(normalized_key, content_type=content_type, visibility=visibility)

    def open_read(self, key: str) -> BinaryIO:
        return self.resolve_path(key).open("rb")

    def exists(self, key: str) -> bool:
        return self.resolve_path(key).exists()

    def delete(self, key: str) -> bool:
        path = self.resolve_path(key)
        if not path.exists():
            return False
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return True

    def get_uri(self, key: str) -> str:
        normalized_key = normalize_storage_key(key)
        if self.public_base_url:
            return f"{self.public_base_url}/{normalized_key}"
        return str(self.resolve_path(normalized_key))

    def get_signed_url(self, key: str, *, expires_seconds: int = 300) -> str:
        raise NotImplementedError("local storage does not issue signed URLs")

    def copy(self, source_key: str, destination_key: str) -> StorageObject:
        source_path = self.resolve_path(source_key)
        if not source_path.exists():
            raise StorageObjectNotFoundError(source_key)
        return self.save_file(destination_key, source_path)

    def stat(
        self,
        key: str,
        *,
        content_type: str | None = None,
        visibility: str = "private",
    ) -> StorageObject:
        normalized_key = normalize_storage_key(key)
        path = self.resolve_path(normalized_key)
        if not path.exists():
            raise StorageObjectNotFoundError(normalized_key)
        data = path.read_bytes() if path.is_file() else b""
        return StorageObject(
            key=normalized_key,
            path=path,
            uri=self.get_uri(normalized_key),
            size_bytes=path.stat().st_size if path.is_file() else 0,
            content_type=content_type,
            checksum=hashlib.sha256(data).hexdigest() if path.is_file() else None,
            storage_backend=self.backend_name,
            visibility=visibility,
            created_at=datetime.fromtimestamp(path.stat().st_ctime).astimezone(),
        )

    def cleanup_prefix(
        self,
        prefix: str,
        *,
        dry_run: bool = True,
        max_delete_count: int = 100,
    ) -> list[str]:
        normalized_prefix = normalize_storage_key(prefix)
        root = self.resolve_path(normalized_prefix)
        if not root.exists():
            return []
        if not root.is_dir():
            candidates = [root]
        else:
            candidates = list(root.rglob("*"))
            candidates.sort(key=lambda item: len(item.parts), reverse=True)
        if len(candidates) > max_delete_count:
            raise InvalidStorageKeyError("cleanup max delete count exceeded")
        deleted: list[str] = []
        for candidate in candidates:
            if candidate == root and root.is_dir():
                continue
            if dry_run:
                deleted.append(self._relative_key(candidate))
                continue
            if candidate.is_dir():
                try:
                    candidate.rmdir()
                except OSError:
                    continue
            else:
                candidate.unlink()
            deleted.append(self._relative_key(candidate))
        if not dry_run and root.is_dir():
            try:
                root.rmdir()
            except OSError:
                pass
        return deleted

    def resolve_path(self, key: str) -> Path:
        normalized_key = normalize_storage_key(key)
        root = self.root.resolve()
        candidate = root.joinpath(*normalized_key.split("/")).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise InvalidStorageKeyError("storage key escapes local root") from exc
        return candidate

    def _relative_key(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError as exc:
            raise InvalidStorageKeyError("path escapes local root") from exc
