from __future__ import annotations

import base64
import binascii
import hashlib
import io
import mimetypes
from dataclasses import dataclass
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from app.config import settings
from app.modules.account_onboarding.errors import artifact_too_large, artifact_unsafe

MAX_ARTIFACT_BYTES = 25 * 1024 * 1024
MAX_ARTIFACT_BASE64_CHARS = ((MAX_ARTIFACT_BYTES + 2) // 3) * 4
MAX_ARCHIVE_FILES = 2000
MAX_ARCHIVE_DEPTH = 16
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
ZIP_REQUIRED_SOURCE_TYPES = {"tdlib_directory", "tdata_archive"}


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    object_key: str
    sha256: str
    size_bytes: int
    content_type_detected: str


def decode_upload(content_base64: str) -> bytes:
    if len(content_base64) > MAX_ARTIFACT_BASE64_CHARS:
        raise artifact_too_large(MAX_ARTIFACT_BYTES)
    try:
        data = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise artifact_unsafe("archive_invalid", "Artifact body is not valid base64.") from exc
    if not data:
        raise artifact_unsafe("archive_missing", "Artifact body is empty.")
    if len(data) > MAX_ARTIFACT_BYTES:
        raise artifact_too_large(MAX_ARTIFACT_BYTES)
    return data


def store_private_artifact(
    *, workspace_id: str, artifact_id: str, filename: str, source_type: str, data: bytes
) -> StoredArtifact:
    if source_type in ZIP_REQUIRED_SOURCE_TYPES and not _looks_like_zip(filename, data):
        raise artifact_unsafe(
            "archive_required",
            "TDLib and tdata artifacts must be uploaded as ZIP archives.",
        )
    if source_type in {"tdlib_directory", "tdata_archive", "session_file"}:
        validate_archive_if_zip(filename, data)
    digest = hashlib.sha256(data).hexdigest()
    object_key = f"account-onboarding/{workspace_id}/{artifact_id}/{digest}"
    path = settings.storage_root / "private" / object_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return StoredArtifact(object_key, digest, len(data), detect_content_type(filename, data))


def detect_content_type(filename: str, data: bytes) -> str:
    if data.startswith(b"PK"):
        return "application/zip"
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def validate_archive_if_zip(filename: str, data: bytes) -> None:
    if not _looks_like_zip(filename, data):
        return
    try:
        with ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
    except BadZipFile as exc:
        raise artifact_unsafe("archive_invalid", "Archive is invalid.") from exc
    if len(infos) > MAX_ARCHIVE_FILES:
        raise artifact_unsafe("archive_rejected_too_many_files", "Archive contains too many files.")
    total = 0
    for info in infos:
        name = info.filename.replace("\\", "/")
        path = PurePosixPath(name)
        if (
            not name
            or name.startswith("/")
            or path.is_absolute()
            or any(part == ".." for part in path.parts)
        ):
            raise artifact_unsafe("archive_rejected_unsafe_path", "Archive contains unsafe paths.")
        if len([part for part in path.parts if part not in {"", "."}]) > MAX_ARCHIVE_DEPTH:
            raise artifact_unsafe("archive_rejected_too_deep", "Archive nesting is too deep.")
        mode = (info.external_attr >> 16) & 0o170000
        if mode == 0o120000:
            raise artifact_unsafe("archive_rejected_symlink", "Archive contains symlinks.")
        total += info.file_size
        if total > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise artifact_unsafe(
                "archive_rejected_too_large", "Archive uncompressed size is too large."
            )


def _looks_like_zip(filename: str, data: bytes) -> bool:
    return filename.lower().endswith(".zip") or data.startswith(b"PK")
