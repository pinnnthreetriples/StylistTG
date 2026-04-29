from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.schemas import AssetRead
from app.models import AssetKind
from app.services.assets import (
    get_asset,
    save_profile_audio_asset,
    save_profile_photo_asset,
    save_story_image_asset,
    save_story_video_asset,
)

router = APIRouter(prefix="/api/assets", tags=["assets"])
STORAGE_ROOT = Path(settings.local_storage_path)


@router.post("/profile-photo", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def post_profile_photo(file: UploadFile = File(...), session: Session = Depends(get_session)):
    content = await _read_upload_limited(file, settings.profile_photo_max_bytes)
    try:
        return save_profile_photo_asset(
            session,
            filename=file.filename or "profile-photo",
            content=content,
            storage_root=STORAGE_ROOT,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/profile-audio", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def post_profile_audio(file: UploadFile = File(...), session: Session = Depends(get_session)):
    content = await _read_upload_limited(file, settings.profile_audio_max_bytes)
    try:
        return save_profile_audio_asset(
            session,
            filename=file.filename or "profile-audio",
            content=content,
            storage_root=STORAGE_ROOT,
            max_bytes=settings.profile_audio_max_bytes,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_asset_upload_error(str(exc)),
        ) from exc


@router.post("/story-image", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def post_story_image(file: UploadFile = File(...), session: Session = Depends(get_session)):
    content = await _read_upload_limited(file, settings.story_image_max_bytes)
    try:
        return save_story_image_asset(
            session,
            filename=file.filename or "story-image",
            content=content,
            storage_root=STORAGE_ROOT,
            max_bytes=settings.story_image_max_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/story-video", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def post_story_video(file: UploadFile = File(...), session: Session = Depends(get_session)):
    content = await _read_upload_limited(file, settings.story_video_max_bytes)
    try:
        return save_story_video_asset(
            session,
            filename=file.filename or "story-video",
            content=content,
            storage_root=STORAGE_ROOT,
            max_bytes=settings.story_video_max_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{asset_id}", response_model=AssetRead)
def get_asset_endpoint(asset_id: str, session: Session = Depends(get_session)):
    asset = get_asset(session, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")
    return asset


@router.get("/{asset_id}/content")
def get_asset_content(asset_id: str, session: Session = Depends(get_session)):
    asset = get_asset(session, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")

    path = STORAGE_ROOT / asset.normalized_path
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset content not found")

    media_type = "image/jpeg" if asset.kind == AssetKind.PROFILE_PHOTO else asset.mime
    return FileResponse(path, media_type=media_type)


async def _read_upload_limited(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail={
                    "error_code": "UPLOAD_TOO_LARGE",
                    "error_class": "validation",
                    "message": "uploaded file is too large",
                    "details": {"max_bytes": max_bytes},
                },
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _asset_upload_error(message: str) -> dict:
    if message == "profile audio must be MP3 or M4A":
        return {
            "error_code": "PROFILE_AUDIO_UNSUPPORTED_FORMAT",
            "error_class": "validation",
            "message": message,
        }
    return {
        "error_code": "VALIDATION_ERROR",
        "error_class": "validation",
        "message": message,
    }
