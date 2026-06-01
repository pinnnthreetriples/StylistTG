from __future__ import annotations

from pathlib import Path
from typing import cast

from app.adapters.tdlib_auth import TdlibClient
from app.config import Settings
from sqlalchemy.orm import Session
from app.modules.account_profile_state.audio import (
    clear_profile_audio_state,
    upsert_profile_audio_state,
)
from app.services.assets import save_profile_audio_asset, save_profile_photo_asset

from .sync_payloads import _send_query_checked
from .sync_types import JsonDict, JsonList


def _fetch_profile_photo(
    client: TdlibClient, user_id: object, full_info: JsonDict, config: Settings
) -> JsonDict | None:
    photos = _send_query_checked(
        client,
        {"@type": "getUserProfilePhotos", "user_id": user_id, "offset": 0, "limit": 1},
        config.tdlib_auth_timeout_seconds,
    )
    source = (photos.get("photos") or [None])[0] or full_info.get("photo")
    file = _largest_file(source)
    content = _download_file_bytes(client, file, config)
    if content is None:
        return None
    return {"content": content, "filename": "telegram-profile-photo.jpg", "raw_tdlib_json": source}


def _fetch_profile_audio(
    client: TdlibClient, user_id: object, full_info: JsonDict, config: Settings
) -> JsonDict | None:
    audios = _send_query_checked(
        client,
        {"@type": "getUserProfileAudios", "user_id": user_id, "offset": 0, "limit": 1},
        config.tdlib_auth_timeout_seconds,
    )
    audio = (audios.get("audios") or [None])[0] or full_info.get("first_profile_audio")
    if not isinstance(audio, dict):
        return None
    audio_payload = cast(JsonDict, audio)
    file_value = audio_payload.get("audio")
    file = (
        cast(JsonDict, file_value) if isinstance(file_value, dict) else _largest_file(audio_payload)
    )
    content = _download_file_bytes(client, file, config)
    return {
        "telegram_audio_id": str(audio_payload.get("id"))
        if audio_payload.get("id") is not None
        else None,
        "telegram_file_id": str(file.get("id"))
        if isinstance(file, dict) and file.get("id") is not None
        else None,
        "title": audio_payload.get("title") or None,
        "performer": audio_payload.get("performer") or None,
        "duration_seconds": audio_payload.get("duration"),
        "mime": audio_payload.get("mime_type") or "audio/mpeg",
        "filename": _audio_filename(audio_payload),
        "content": content,
        "raw_tdlib_json": audio_payload,
    }


def _download_file_bytes(client: TdlibClient, file: object, config: Settings) -> bytes | None:
    if not isinstance(file, dict):
        return None
    file_payload = cast(JsonDict, file)
    if not isinstance(file_payload.get("id"), int):
        return None
    downloaded = _send_query_checked(
        client,
        {
            "@type": "downloadFile",
            "file_id": file_payload["id"],
            "priority": 16,
            "offset": 0,
            "limit": 0,
            "synchronous": True,
        },
        config.tdlib_auth_timeout_seconds,
    )
    local_value = downloaded.get("local")
    local = cast(JsonDict, local_value) if isinstance(local_value, dict) else {}
    path = local.get("path")
    if not isinstance(path, str) or not path:
        return None
    file_path = Path(path)
    if not file_path.exists():
        return None
    return file_path.read_bytes()


def _largest_file(value: object) -> JsonDict | None:
    files: JsonList = []
    _collect_files(value, files)
    if not files:
        return None
    return max(files, key=lambda item: int(item.get("expected_size") or item.get("size") or 0))


def _collect_files(value: object, files: JsonList) -> None:
    if isinstance(value, dict):
        payload = cast(JsonDict, value)
        if payload.get("@type") == "file" and isinstance(payload.get("id"), int):
            files.append(payload)
        for nested in payload.values():
            _collect_files(nested, files)
    elif isinstance(value, list):
        values = cast(list[object], value)
        for nested in values:
            _collect_files(nested, files)


def _audio_filename(audio: JsonDict) -> str:
    file_name = audio.get("file_name")
    if isinstance(file_name, str) and file_name:
        return file_name
    title = audio.get("title")
    if isinstance(title, str) and title:
        return f"{title}.mp3"
    return "telegram-profile-audio.mp3"


def _save_synced_profile_photo(
    session: Session,
    *,
    account_id: str,
    photo: object,
    config: Settings,
) -> str | None:
    if not isinstance(photo, dict):
        return None
    photo_payload = cast(JsonDict, photo)
    if not isinstance(photo_payload.get("content"), bytes):
        return None
    asset = save_profile_photo_asset(
        session,
        filename=str(photo_payload.get("filename") or "telegram-profile-photo.jpg"),
        content=photo_payload["content"],
        storage_root=config.storage_root,
    )
    return asset.id


def _sync_profile_audio_state(
    session: Session,
    *,
    account_id: str,
    audio: object,
    config: Settings,
) -> None:
    if not isinstance(audio, dict):
        clear_profile_audio_state(session, account_id=account_id)
        return
    audio_payload = cast(JsonDict, audio)

    source_asset_id = None
    if isinstance(audio_payload.get("content"), bytes):
        try:
            asset = save_profile_audio_asset(
                session,
                filename=str(audio_payload.get("filename") or "telegram-profile-audio.mp3"),
                content=audio_payload["content"],
                storage_root=config.storage_root,
                max_bytes=config.profile_audio_max_bytes,
            )
            source_asset_id = asset.id
        except ValueError:
            source_asset_id = None

    upsert_profile_audio_state(
        session,
        account_id=account_id,
        telegram_file_id=audio_payload.get("telegram_file_id"),
        source_asset_id=source_asset_id,
        title=audio_payload.get("title"),
        performer=audio_payload.get("performer"),
        duration_seconds=audio_payload.get("duration_seconds"),
        mime=audio_payload.get("mime"),
        telegram_audio_id=audio_payload.get("telegram_audio_id"),
        raw_tdlib_json=audio_payload.get("raw_tdlib_json"),
    )
