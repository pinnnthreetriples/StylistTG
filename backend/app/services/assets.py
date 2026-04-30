from __future__ import annotations

import hashlib
import shutil
import subprocess
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.models import DEFAULT_LOCAL_WORKSPACE_ID, Asset, AssetKind, AssetStatus, new_id
from app.services.audit_logs import log_audit_event

PROFILE_AUDIO_EXECUTION_MIMES = {
    "audio/mpeg",
    "audio/mp4",
}

STORY_VIDEO_ALLOWED_MIMES = {"video/mp4", "video/quicktime", "video/webm"}


def save_profile_photo_asset(
    session: Session,
    *,
    filename: str,
    content: bytes,
    storage_root: Path,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    actor_user_id: str | None = None,
) -> Asset:
    asset_id = new_id()
    source_dir = storage_root / "assets" / asset_id / "source"
    normalized_dir = storage_root / "assets" / asset_id / "normalized"
    source_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    try:
        image = Image.open(BytesIO(content))
        image.verify()
        image = Image.open(BytesIO(content))
    except UnidentifiedImageError as exc:
        raise ValueError("uploaded file is not a supported image") from exc

    mime = Image.MIME.get(image.format or "", "application/octet-stream")
    source_name = f"original{Path(filename).suffix or '.upload'}"
    source_path = source_dir / source_name
    source_path.write_bytes(content)

    normalized = ImageOps.exif_transpose(image).convert("RGB")
    normalized.thumbnail((1024, 1024))
    normalized_path = normalized_dir / "profile_photo.jpg"
    normalized.save(normalized_path, format="JPEG", quality=90, optimize=True)
    content_hash = hashlib.sha256(normalized_path.read_bytes()).hexdigest()

    asset = Asset(
        id=asset_id,
        workspace_id=workspace_id,
        kind=AssetKind.PROFILE_PHOTO,
        source_path=str(source_path.relative_to(storage_root)),
        normalized_path=str(normalized_path.relative_to(storage_root)),
        original_filename=filename,
        content_hash=content_hash,
        mime=mime,
        status=AssetStatus.NORMALIZED,
    )
    session.add(asset)
    _log_asset_uploaded(session, asset=asset, workspace_id=workspace_id, actor_user_id=actor_user_id)
    session.commit()
    session.refresh(asset)
    return asset


def save_profile_audio_asset(
    session: Session,
    *,
    filename: str,
    content: bytes,
    storage_root: Path,
    max_bytes: int,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    actor_user_id: str | None = None,
) -> Asset:
    if not content:
        raise ValueError("uploaded file is empty")
    if len(content) > max_bytes:
        raise ValueError("uploaded audio is too large")

    mime = _guess_audio_mime(filename, content)
    if mime not in PROFILE_AUDIO_EXECUTION_MIMES:
        raise ValueError("profile audio must be MP3 or M4A")

    asset_id = new_id()
    source_dir = storage_root / "assets" / asset_id / "source"
    normalized_dir = storage_root / "assets" / asset_id / "normalized"
    source_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    extension = Path(filename).suffix or _audio_extension_for_mime(mime)
    source_path = source_dir / f"original{extension}"
    normalized_path = normalized_dir / f"profile_audio{extension}"
    source_path.write_bytes(content)
    normalized_path.write_bytes(content)
    content_hash = hashlib.sha256(content).hexdigest()

    asset = Asset(
        id=asset_id,
        workspace_id=workspace_id,
        kind=AssetKind.PROFILE_AUDIO,
        source_path=str(source_path.relative_to(storage_root)),
        normalized_path=str(normalized_path.relative_to(storage_root)),
        original_filename=filename,
        content_hash=content_hash,
        mime=mime,
        status=AssetStatus.NORMALIZED,
    )
    session.add(asset)
    _log_asset_uploaded(session, asset=asset, workspace_id=workspace_id, actor_user_id=actor_user_id)
    session.commit()
    session.refresh(asset)
    return asset


def save_story_image_asset(
    session: Session,
    *,
    filename: str,
    content: bytes,
    storage_root: Path,
    max_bytes: int,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    actor_user_id: str | None = None,
) -> Asset:
    if not content:
        raise ValueError("uploaded file is empty")
    if len(content) > max_bytes:
        raise ValueError("uploaded story image is too large")

    asset_id = new_id()
    source_dir = storage_root / "assets" / asset_id / "source"
    normalized_dir = storage_root / "assets" / asset_id / "normalized"
    source_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    try:
        image = Image.open(BytesIO(content))
        image.verify()
        image = Image.open(BytesIO(content))
    except UnidentifiedImageError as exc:
        raise ValueError("uploaded file is not a supported story image") from exc

    source_path = source_dir / f"original{Path(filename).suffix or '.upload'}"
    source_path.write_bytes(content)
    normalized = ImageOps.exif_transpose(image).convert("RGB")
    normalized.thumbnail((1080, 1920))
    normalized_path = normalized_dir / "story_image.jpg"
    normalized.save(normalized_path, format="JPEG", quality=90, optimize=True)
    content_hash = hashlib.sha256(normalized_path.read_bytes()).hexdigest()

    asset = Asset(
        id=asset_id,
        workspace_id=workspace_id,
        kind=AssetKind.STORY_IMAGE,
        source_path=str(source_path.relative_to(storage_root)),
        normalized_path=str(normalized_path.relative_to(storage_root)),
        original_filename=filename,
        content_hash=content_hash,
        mime="image/jpeg",
        status=AssetStatus.NORMALIZED,
    )
    session.add(asset)
    _log_asset_uploaded(session, asset=asset, workspace_id=workspace_id, actor_user_id=actor_user_id)
    session.commit()
    session.refresh(asset)
    return asset


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
) -> Asset:
    if not content:
        raise ValueError("uploaded file is empty")
    if len(content) > max_bytes:
        raise ValueError("uploaded story video is too large")
    mime = _guess_story_video_mime(filename, content)
    if mime not in STORY_VIDEO_ALLOWED_MIMES:
        raise ValueError("uploaded file is not a supported story video")

    asset_id = new_id()
    source_dir = storage_root / "assets" / asset_id / "source"
    normalized_dir = storage_root / "assets" / asset_id / "normalized"
    source_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    extension = Path(filename).suffix or ".mp4"
    source_path = source_dir / f"original{extension}"
    asset_root = storage_root / "assets" / asset_id
    try:
        source_path.write_bytes(content)
        normalized_path = _prepare_story_video(source_path, normalized_dir, config)
    except Exception:
        shutil.rmtree(asset_root, ignore_errors=True)
        raise
    content_hash = hashlib.sha256(normalized_path.read_bytes()).hexdigest()

    asset = Asset(
        id=asset_id,
        workspace_id=workspace_id,
        kind=AssetKind.STORY_VIDEO,
        source_path=str(source_path.relative_to(storage_root)),
        normalized_path=str(normalized_path.relative_to(storage_root)),
        original_filename=filename,
        content_hash=content_hash,
        mime=mime,
        status=AssetStatus.NORMALIZED,
    )
    session.add(asset)
    _log_asset_uploaded(session, asset=asset, workspace_id=workspace_id, actor_user_id=actor_user_id)
    session.commit()
    session.refresh(asset)
    return asset


def get_asset(session: Session, asset_id: str) -> Asset | None:
    return session.get(Asset, asset_id)


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


def _guess_audio_mime(filename: str, content: bytes) -> str:
    if content.startswith(b"ID3") or content[:2] == b"\xff\xfb":
        return "audio/mpeg"
    if content.startswith(b"OggS"):
        return "audio/ogg"
    if content.startswith(b"RIFF") and content[8:12] == b"WAVE":
        return "audio/wav"
    if len(content) >= 12 and content[4:8] == b"ftyp":
        return "audio/mp4"
    return "application/octet-stream"


def _audio_extension_for_mime(mime: str) -> str:
    return {
        "audio/aac": ".aac",
        "audio/flac": ".flac",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/ogg": ".ogg",
        "application/ogg": ".ogg",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
    }.get(mime, ".audio")


def _guess_story_video_mime(filename: str, content: bytes) -> str:
    if len(content) >= 12 and content[4:8] == b"ftyp":
        major_brand = content[8:12]
        if major_brand in {b"qt  "}:
            return "video/quicktime"
        return "video/mp4"
    if content.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    return "application/octet-stream"


def _prepare_story_video(source_path: Path, normalized_dir: Path, config: Settings) -> Path:
    ffprobe = config.ffprobe_path or "ffprobe"
    ffmpeg = config.ffmpeg_path or "ffmpeg"
    if not _command_available(ffprobe) or not _command_available(ffmpeg):
        raise ValueError("story video preparation requires ffprobe and ffmpeg")

    _validate_story_video_file_with_ffprobe(source_path, ffprobe)
    normalized_path = normalized_dir / "story_video.mp4"
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(source_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            "scale='min(1080,iw)':'min(1920,ih)':force_original_aspect_ratio=decrease",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(normalized_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0 or not normalized_path.exists():
        raise ValueError("uploaded story video could not be normalized")
    return normalized_path


def _validate_story_video_file_with_ffprobe(path: Path, ffprobe: str) -> None:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0 or "video" not in result.stdout:
        raise ValueError("uploaded file is not a valid story video")


def _command_available(command: str) -> bool:
    try:
        result = subprocess.run(
            [command, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0
