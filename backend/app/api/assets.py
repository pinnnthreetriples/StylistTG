from pathlib import Path
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.services.auth_context import (
    AuthContext,
    require_authenticated,
    require_mutation_permission,
)
from app.schemas import AssetRead
from app.models import Asset, AssetKind
from app.services.asset_storage import asset_normalized_storage_key, get_asset_signed_url
from app.services.assets import (
    get_asset,
    save_profile_audio_asset,
    save_profile_photo_asset,
    save_story_image_asset,
    save_story_video_asset_from_path,
)
from app.storage import LocalStorageService, StorageService, build_storage_service

router = APIRouter(prefix="/api/assets", tags=["assets"])
STORAGE_ROOT = Path(settings.storage_root)


@router.post("/profile-photo", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def post_profile_photo(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    content = await _read_upload_limited(file, settings.profile_photo_max_bytes)
    try:
        return save_profile_photo_asset(
            session,
            filename=file.filename or "profile-photo",
            content=content,
            storage_root=STORAGE_ROOT,
            storage_service=_asset_storage(),
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/profile-audio", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def post_profile_audio(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    content = await _read_upload_limited(file, settings.profile_audio_max_bytes)
    try:
        return save_profile_audio_asset(
            session,
            filename=file.filename or "profile-audio",
            content=content,
            storage_root=STORAGE_ROOT,
            storage_service=_asset_storage(),
            max_bytes=settings.profile_audio_max_bytes,
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_asset_upload_error(str(exc)),
        ) from exc


@router.post("/story-image", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def post_story_image(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    content = await _read_upload_limited(file, settings.story_image_max_bytes)
    try:
        return save_story_image_asset(
            session,
            filename=file.filename or "story-image",
            content=content,
            storage_root=STORAGE_ROOT,
            storage_service=_asset_storage(),
            max_bytes=settings.story_image_max_bytes,
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/story-video", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def post_story_video(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    with tempfile.TemporaryDirectory(prefix="stylisttg-story-video-upload-") as temp_dir:
        source_path = Path(temp_dir) / f"original{Path(file.filename or 'story-video').suffix or '.mp4'}"
        await _read_upload_to_path_limited(file, source_path, settings.story_video_max_bytes)
        try:
            return save_story_video_asset_from_path(
                session,
                filename=file.filename or "story-video",
                source_path=source_path,
                storage_root=STORAGE_ROOT,
                storage_service=_asset_storage(),
                max_bytes=settings.story_video_max_bytes,
                workspace_id=auth.workspace_id,
                actor_user_id=auth.user_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{asset_id}", response_model=AssetRead)
def get_asset_endpoint(
    asset_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    asset = get_asset(session, asset_id)
    if asset is None or asset.workspace_id != auth.workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")
    return asset


@router.get("/{asset_id}/content")
def get_asset_content(
    asset_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    asset = get_asset(session, asset_id)
    if asset is None or asset.workspace_id != auth.workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")

    storage = _asset_storage()
    if not isinstance(storage, LocalStorageService):
        media_type = _asset_media_type(asset)
        try:
            return StreamingResponse(
                storage.open_read(asset_normalized_storage_key(asset)),
                media_type=media_type,
            )
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="asset content not found"
            ) from exc
    path = storage.resolve_path(asset_normalized_storage_key(asset))
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset content not found")

    media_type = _asset_media_type(asset)
    return FileResponse(path, media_type=media_type)


@router.get("/{asset_id}/signed-url")
def get_asset_signed_url_endpoint(
    asset_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, str | int]:
    asset = get_asset(session, asset_id)
    if asset is None or asset.workspace_id != auth.workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")
    try:
        return {
            "asset_id": asset.id,
            "url": get_asset_signed_url(asset, config=settings, storage=_asset_storage()),
            "expires_seconds": settings.storage_s3_signed_url_expires_seconds,
        }
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="signed URLs are not available"
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="asset content not found"
        ) from exc


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


async def _read_upload_to_path_limited(file: UploadFile, path: Path, max_bytes: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with path.open("wb") as handle:
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
            handle.write(chunk)


def _asset_upload_error(message: str) -> dict[str, str]:
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


def _asset_storage() -> StorageService:
    if settings.storage_backend == "local":
        return LocalStorageService(STORAGE_ROOT, public_base_url=settings.storage_public_base_url)
    return build_storage_service(settings)


def _asset_media_type(asset: Asset) -> str:
    return "image/jpeg" if asset.kind == AssetKind.PROFILE_PHOTO else asset.mime
