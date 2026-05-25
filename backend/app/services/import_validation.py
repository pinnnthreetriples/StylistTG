from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any

from app.config import Settings, settings
from app.services.phone_hints import phone_hint

SUPPORTED_IMPORT_SOURCE_TYPES = {"tdlib-directory", "tdata", "session-file", "json-metadata"}


@dataclass(frozen=True)
class ImportValidationItem:
    status: str
    validation_code: str
    validation_message: str
    risk_level: str = "medium"
    phone_hint: str | None = None
    username_hint: str | None = None
    source_ref_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "validation_code": self.validation_code,
            "validation_message": self.validation_message,
            "risk_level": self.risk_level,
            "phone_hint": self.phone_hint,
            "username_hint": self.username_hint,
            "source_ref_hash": self.source_ref_hash,
        }


def validate_import_source(
    *,
    source_type: str,
    content: bytes | None = None,
    metadata: dict[str, Any] | None = None,
    config: Settings = settings,
) -> list[ImportValidationItem]:
    if source_type not in SUPPORTED_IMPORT_SOURCE_TYPES:
        return [_unsupported("unsupported_source_type", "Unsupported account import source type.")]
    if source_type == "json-metadata":
        return [_validate_json_metadata(content=content, metadata=metadata)]
    if source_type in {"tdlib-directory", "tdata"}:
        return [
            _validate_archive_structure(source_type=source_type, content=content, config=config)
        ]
    return [
        _unsupported(
            "unsupported_source_requires_manual_reauth",
            "Session file imports require manual reauthorization.",
        )
    ]


def _validate_json_metadata(
    *, content: bytes | None, metadata: dict[str, Any] | None
) -> ImportValidationItem:
    payload = metadata or {}
    if content:
        try:
            payload = json.loads(content.decode("utf-8"))
        except UnicodeDecodeError, json.JSONDecodeError:
            return _unsupported("json_metadata_invalid", "JSON metadata is not valid.")
    username = _safe_hint(payload.get("username"))
    phone = phone_hint(payload.get("phone") or payload.get("phone_number"))
    return ImportValidationItem(
        status="valid",
        validation_code="json_metadata_preview",
        validation_message="JSON metadata can be previewed; Telegram authorization is still required.",
        risk_level="low",
        phone_hint=phone,
        username_hint=username,
        source_ref_hash=_hash_source(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ),
    )


def _validate_archive_structure(
    *, source_type: str, content: bytes | None, config: Settings
) -> ImportValidationItem:
    if not content:
        return _unsupported("archive_missing", "Upload an archive for this source type.")
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            infos = archive.infolist()
            _validate_archive_infos(infos, config=config)
    except (zipfile.BadZipFile, ValueError) as exc:
        return _unsupported("archive_rejected", str(exc))
    code = (
        "tdlib_structure_detected"
        if source_type == "tdlib-directory"
        else "tdata_structure_detected"
    )
    return ImportValidationItem(
        status="valid" if source_type == "tdlib-directory" else "unsupported",
        validation_code=code
        if source_type == "tdlib-directory"
        else "unsupported_source_requires_manual_reauth",
        validation_message="Archive structure is safe for dry-run validation; manual Telegram verification remains required.",
        risk_level="medium",
        source_ref_hash=_hash_source(
            "\n".join(sorted(info.filename for info in infos)).encode("utf-8")
        ),
    )


def _validate_archive_infos(infos: list[zipfile.ZipInfo], *, config: Settings) -> None:
    if len(infos) > config.account_import_max_file_count:
        raise ValueError("archive contains too many files")
    total_size = 0
    for info in infos:
        path = PurePosixPath(info.filename.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("archive contains unsafe paths")
        if len(path.parts) > config.account_import_max_depth:
            raise ValueError("archive nesting is too deep")
        if _zip_info_is_symlink(info):
            raise ValueError("archive contains symlinks")
        total_size += max(info.file_size, 0)
        if total_size > config.account_import_max_uncompressed_bytes:
            raise ValueError("archive is too large")


def _zip_info_is_symlink(info: zipfile.ZipInfo) -> bool:
    unix_mode = info.external_attr >> 16
    return (unix_mode & 0o170000) == 0o120000


def _unsupported(code: str, message: str) -> ImportValidationItem:
    return ImportValidationItem(
        status="unsupported", validation_code=code, validation_message=message, risk_level="high"
    )


def _hash_source(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_hint(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value[:64]
