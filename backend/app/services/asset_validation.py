"""Asset validation, MIME guessing, and story-video preparation helpers."""

from __future__ import annotations

import subprocess
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from PIL.Image import DecompressionBombError

from app.config import Settings

PROFILE_AUDIO_EXECUTION_MIMES = {
    "audio/mpeg",
    "audio/mp4",
}

STORY_VIDEO_ALLOWED_MIMES = {"video/mp4", "video/quicktime", "video/webm"}
MAX_IMAGE_PIXELS = 24_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
_COMMAND_PROBE_ERRORS = (OSError, subprocess.TimeoutExpired)


def guess_audio_mime(filename: str, content: bytes) -> str:
    if content.startswith(b"ID3") or content[:2] == b"\xff\xfb":
        return "audio/mpeg"
    if content.startswith(b"OggS"):
        return "audio/ogg"
    if content.startswith(b"RIFF") and content[8:12] == b"WAVE":
        return "audio/wav"
    if len(content) >= 12 and content[4:8] == b"ftyp":
        return "audio/mp4"
    return "application/octet-stream"


def open_verified_image(content: bytes, *, error_message: str) -> Image.Image:
    try:
        image = Image.open(BytesIO(content))
        enforce_image_pixel_limit(image)
        image.verify()
        image = Image.open(BytesIO(content))
        enforce_image_pixel_limit(image)
        image.load()
        return image
    except (UnidentifiedImageError, DecompressionBombError, OSError) as exc:
        raise ValueError(error_message) from exc


def enforce_image_pixel_limit(image: Image.Image) -> None:
    width, height = image.size
    if width * height > MAX_IMAGE_PIXELS:
        raise DecompressionBombError("uploaded image exceeds pixel limit")


def audio_extension_for_mime(mime: str) -> str:
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


def guess_story_video_mime(filename: str, content: bytes) -> str:
    if len(content) >= 12 and content[4:8] == b"ftyp":
        major_brand = content[8:12]
        if major_brand in {b"qt  "}:
            return "video/quicktime"
        return "video/mp4"
    if content.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    return "application/octet-stream"


def prepare_story_video(source_path: Path, normalized_dir: Path, config: Settings) -> Path:
    ffprobe = config.ffprobe_path or "ffprobe"
    ffmpeg = config.ffmpeg_path or "ffmpeg"
    if not command_available(ffprobe) or not command_available(ffmpeg):
        raise ValueError("story video preparation requires ffprobe and ffmpeg")

    validate_story_video_file_with_ffprobe(source_path, ffprobe)
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


def validate_story_video_file_with_ffprobe(path: Path, ffprobe: str) -> None:
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


def validate_content_not_empty(content: bytes, *, label: str) -> None:
    if not content:
        raise ValueError("uploaded file is empty")


def validate_file_not_empty(path: Path, *, label: str) -> None:
    if path.stat().st_size <= 0:
        raise ValueError("uploaded file is empty")


def validate_content_size(content: bytes, max_bytes: int, *, label: str) -> None:
    if len(content) > max_bytes:
        raise ValueError(f"uploaded {label} is too large")


def validate_file_size(path: Path, max_bytes: int, *, label: str) -> None:
    if path.stat().st_size > max_bytes:
        raise ValueError(f"uploaded {label} is too large")


def read_file_prefix(path: Path, size: int = 32) -> bytes:
    with path.open("rb") as handle:
        return handle.read(size)


def command_available(command: str) -> bool:
    try:
        result = subprocess.run(
            [command, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except _COMMAND_PROBE_ERRORS:
        return False
    return result.returncode == 0


__all__ = [
    "PROFILE_AUDIO_EXECUTION_MIMES",
    "STORY_VIDEO_ALLOWED_MIMES",
    "audio_extension_for_mime",
    "guess_audio_mime",
    "guess_story_video_mime",
    "open_verified_image",
    "prepare_story_video",
    "read_file_prefix",
    "validate_content_not_empty",
    "validate_content_size",
    "validate_file_not_empty",
    "validate_file_size",
]
