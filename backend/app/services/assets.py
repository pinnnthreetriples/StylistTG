from __future__ import annotations

import hashlib
import tempfile
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.models import DEFAULT_LOCAL_WORKSPACE_ID, Asset, AssetKind, AssetStatus, new_id, utc_now
from app.services.asset_validation import (
    PROFILE_AUDIO_EXECUTION_MIMES,
    STORY_VIDEO_ALLOWED_MIMES,
    audio_extension_for_mime,
    guess_audio_mime,
    guess_story_video_mime,
    open_verified_image,
    prepare_story_video as _prepare_story_video,
    read_file_prefix,
    validate_content_not_empty,
    validate_content_size,
    validate_file_not_empty,
    validate_file_size,
)
from app.services.audit_logs import log_audit_event
from app.storage.base import StorageObject
from app.storage import LocalStorageService, StorageService
from app.storage.paths import asset_normalized_key, asset_prefix, asset_source_key

def save_profile_photo_asset(
    session: Session,
    *,
    filename: str,
    content: bytes,
    storage_root: Path,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    actor_user_id: str | None = None,
    storage_service: StorageService | None = None,
) -> Asset:
    asset_id, storage = _init_asset_storage(storage_root, storage_service)

    image = open_verified_image(content, error_message="uploaded file is not a supported image")

    mime = Image.MIME.get(image.format or "", "application/octet-stream")
    source_name = f"original{Path(filename).suffix or '.upload'}"
    source_key = asset_source_key(asset_id, source_name)
    source_object = storage.save_bytes(source_key, content, content_type=mime)

    normalized = ImageOps.exif_transpose(image).convert("RGB")
    normalized.thumbnail((1024, 1024))
    normalized_bytes = BytesIO()
    normalized.save(normalized_bytes, format="JPEG", quality=90, optimize=True)
    normalized_content = normalized_bytes.getvalue()
    normalized_key = asset_normalized_key(asset_id, "profile_photo.jpg")
    normalized_object = storage.save_bytes(
        normalized_key, normalized_content, content_type="image/jpeg"
    )
    content_hash = hashlib.sha256(normalized_content).hexdigest()

    return _finalize_asset(
        session,
        asset_id=asset_id,
        workspace_id=workspace_id,
        kind=AssetKind.PROFILE_PHOTO,
        source_key=source_key,
        normalized_key=normalized_key,
        filename=filename,
        content_hash=content_hash,
        mime=mime,
        storage=storage,
        source_object=source_object,
        normalized_object=normalized_object,
        actor_user_id=actor_user_id,
    )


def save_profile_audio_asset(
    session: Session,
    *,
    filename: str,
    content: bytes,
    storage_root: Path,
    max_bytes: int,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    actor_user_id: str | None = None,
    storage_service: StorageService | None = None,
) -> Asset:
    validate_content_not_empty(content, label="audio")
    validate_content_size(content, max_bytes, label="audio")

    mime = guess_audio_mime(filename, content)
    if mime not in PROFILE_AUDIO_EXECUTION_MIMES:
        raise ValueError("profile audio must be MP3 or M4A")

    asset_id, storage = _init_asset_storage(storage_root, storage_service)

    extension = Path(filename).suffix or audio_extension_for_mime(mime)
    source_key = asset_source_key(asset_id, f"original{extension}")
    normalized_key = asset_normalized_key(asset_id, f"profile_audio{extension}")
    source_object = storage.save_bytes(source_key, content, content_type=mime)
    normalized_object = storage.save_bytes(normalized_key, content, content_type=mime)
    content_hash = hashlib.sha256(content).hexdigest()

    return _finalize_asset(
        session,
        asset_id=asset_id,
        workspace_id=workspace_id,
        kind=AssetKind.PROFILE_AUDIO,
        source_key=source_key,
        normalized_key=normalized_key,
        filename=filename,
        content_hash=content_hash,
        mime=mime,
        storage=storage,
        source_object=source_object,
        normalized_object=normalized_object,
        actor_user_id=actor_user_id,
    )


def save_story_image_asset(
    session: Session,
    *,
    filename: str,
    content: bytes,
    storage_root: Path,
    max_bytes: int,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    actor_user_id: str | None = None,
    storage_service: StorageService | None = None,
) -> Asset:
    validate_content_not_empty(content, label="story image")
    validate_content_size(content, max_bytes, label="story image")

    asset_id, storage = _init_asset_storage(storage_root, storage_service)

    image = open_verified_image(
        content, error_message="uploaded file is not a supported story image"
    )

    mime = Image.MIME.get(image.format or "", "application/octet-stream")
    source_key = asset_source_key(asset_id, f"original{Path(filename).suffix or '.upload'}")
    source_object = storage.save_bytes(source_key, content, content_type=mime)
    normalized = ImageOps.exif_transpose(image).convert("RGB")
    normalized.thumbnail((1080, 1920))
    normalized_bytes = BytesIO()
    normalized.save(normalized_bytes, format="JPEG", quality=90, optimize=True)
    normalized_content = normalized_bytes.getvalue()
    normalized_key = asset_normalized_key(asset_id, "story_image.jpg")
    normalized_object = storage.save_bytes(
        normalized_key, normalized_content, content_type="image/jpeg"
    )
    content_hash = hashlib.sha256(normalized_content).hexdigest()

    return _finalize_asset(
        session,
        asset_id=asset_id,
        workspace_id=workspace_id,
        kind=AssetKind.STORY_IMAGE,
        source_key=source_key,
        normalized_key=normalized_key,
        filename=filename,
        content_hash=content_hash,
        mime="image/jpeg",
        storage=storage,
        source_object=source_object,
        normalized_object=normalized_object,
        actor_user_id=actor_user_id,
    )


def save_story_video_asset(
    session: Session,
    *,
    filename: str,
    content: bytes,
    storage_root: Path,
    max_bytes: int,
    config: Settings = settings,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    actor_user_id: str | None = None,
    storage_service: StorageService | None = None,
) -> Asset:
    with tempfile.TemporaryDirectory(prefix="stylisttg-story-video-upload-") as temp_dir:
        source_path = Path(temp_dir) / f"original{Path(filename).suffix or '.mp4'}"
        source_path.write_bytes(content)
        return save_story_video_asset_from_path(
            session,
            filename=filename,
            source_path=source_path,
            storage_root=storage_root,
            max_bytes=max_bytes,
            config=config,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            storage_service=storage_service,
        )


def save_story_video_asset_from_path(
    session: Session,
    *,
    filename: str,
    source_path: Path,
    storage_root: Path,
    max_bytes: int,
    config: Settings = settings,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    actor_user_id: str | None = None,
    storage_service: StorageService | None = None,
) -> Asset:
    validate_file_not_empty(source_path, label="story video")
    validate_file_size(source_path, max_bytes, label="story video")
    mime = guess_story_video_mime(filename, read_file_prefix(source_path))
    if mime not in STORY_VIDEO_ALLOWED_MIMES:
        raise ValueError("uploaded file is not a supported story video")

    asset_id = new_id()
    storage = storage_service or LocalStorageService(storage_root)
    extension = Path(filename).suffix or ".mp4"
    source_key = asset_source_key(asset_id, f"original{extension}")
    normalized_key = asset_normalized_key(asset_id, "story_video.mp4")
    try:
        if isinstance(storage, LocalStorageService):
            source_object = storage.save_file(source_key, source_path, content_type=mime)
            stored_source_path = storage.resolve_path(source_key)
            normalized_dir = storage.resolve_path(asset_normalized_key(asset_id, ".keep")).parent
            normalized_dir.mkdir(parents=True, exist_ok=True)
            normalized_path = _prepare_story_video(stored_source_path, normalized_dir, config)
            normalized_key = normalized_path.relative_to(storage.root.resolve()).as_posix()
            normalized_object = storage.stat(normalized_key, content_type="video/mp4")
        else:
            with tempfile.TemporaryDirectory(prefix="stylisttg-story-video-") as temp_dir:
                temp_root = Path(temp_dir)
                temp_source_path = temp_root / f"original{extension}"
                temp_source_path.write_bytes(source_path.read_bytes())
                normalized_dir = temp_root / "normalized"
                normalized_dir.mkdir(parents=True, exist_ok=True)
                normalized_path = _prepare_story_video(temp_source_path, normalized_dir, config)
                source_object = storage.save_file(source_key, source_path, content_type=mime)
                normalized_object = storage.save_file(
                    normalized_key,
                    normalized_path,
                    content_type="video/mp4",
                )
    except Exception:
        storage.delete(asset_prefix(asset_id))
        raise
    content_hash = (
        normalized_object.checksum or hashlib.sha256(normalized_path.read_bytes()).hexdigest()
    )

    return _finalize_asset(
        session,
        asset_id=asset_id,
        workspace_id=workspace_id,
        kind=AssetKind.STORY_VIDEO,
        source_key=source_key,
        normalized_key=normalized_key,
        filename=filename,
        content_hash=content_hash,
        mime=mime,
        storage=storage,
        source_object=source_object,
        normalized_object=normalized_object,
        actor_user_id=actor_user_id,
    )


def get_asset(
    session: Session, asset_id: str | None, *, workspace_id: str | None = None
) -> Asset | None:
    if not asset_id:
        return None
    if workspace_id is None:
        return session.get(Asset, asset_id)
    return (
        session.execute(
            select(Asset).where(Asset.id == asset_id, Asset.workspace_id == workspace_id)
        )
        .scalars()
        .first()
    )


def _log_asset_uploaded(
    session: Session,
    *,
    asset: Asset,
    workspace_id: str,
    actor_user_id: str | None,
) -> None:
    log_audit_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="asset.uploaded",
        entity_type="asset",
        entity_id=asset.id,
        metadata={"kind": asset.kind, "mime": asset.mime},
    )


def _apply_storage_metadata(
    asset: Asset,
    *,
    storage: StorageService,
    source: StorageObject,
    normalized: StorageObject,
) -> None:
    asset.storage_backend = storage.backend_name
    asset.storage_bucket = getattr(storage, "bucket", None)
    asset.source_key = source.key
    asset.normalized_key = normalized.key
    asset.source_size_bytes = source.size_bytes
    asset.normalized_size_bytes = normalized.size_bytes
    asset.source_content_type = source.content_type
    asset.normalized_content_type = normalized.content_type
    asset.source_checksum = source.checksum
    asset.normalized_checksum = normalized.checksum
    asset.storage_migrated_at = utc_now()


def _init_asset_storage(
    storage_root: Path, storage_service: StorageService | None = None
) -> tuple[str, StorageService]:
    return new_id(), storage_service or LocalStorageService(storage_root)


def _finalize_asset(
    session: Session,
    *,
    asset_id: str,
    workspace_id: str,
    kind: AssetKind,
    source_key: str,
    normalized_key: str,
    filename: str,
    content_hash: str,
    mime: str,
    storage: StorageService,
    source_object: StorageObject,
    normalized_object: StorageObject,
    actor_user_id: str | None = None,
) -> Asset:
    asset = Asset(
        id=asset_id,
        workspace_id=workspace_id,
        kind=kind,
        source_path=source_key,
        normalized_path=normalized_key,
        original_filename=filename,
        content_hash=content_hash,
        mime=mime,
        status=AssetStatus.NORMALIZED,
    )
    _apply_storage_metadata(
        asset, storage=storage, source=source_object, normalized=normalized_object
    )
    session.add(asset)
    _log_asset_uploaded(
        session, asset=asset, workspace_id=workspace_id, actor_user_id=actor_user_id
    )
    session.commit()
    session.refresh(asset)
    return asset
