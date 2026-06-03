from io import BytesIO
from datetime import UTC, datetime

import pytest
from PIL import Image

from app.models import AssetKind, AssetStatus
from app.services.assets import save_profile_audio_asset, save_profile_photo_asset


# test-analyzer: disable=TQA004 reason="asset pipeline contract — verifies normalization metadata fields" permanent="true"
def test_profile_photo_upload_is_normalized_and_recorded(db_session, storage_dir) -> None:
    image = Image.new("RGB", (1600, 900), color=(0, 128, 255))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")

    asset = save_profile_photo_asset(
        db_session,
        filename="profile.jpg",
        content=buffer.getvalue(),
        storage_root=storage_dir,
    )

    assert asset.kind == AssetKind.PROFILE_PHOTO
    assert asset.status == AssetStatus.NORMALIZED
    assert asset.mime == "image/jpeg"
    assert len(asset.content_hash) == 64
    assert (storage_dir / asset.source_path).exists()
    assert (storage_dir / asset.normalized_path).exists()
    assert asset.storage_backend == "local"
    assert asset.source_key == asset.source_path.replace("\\", "/")
    assert asset.normalized_key == asset.normalized_path.replace("\\", "/")
    assert asset.source_size_bytes is not None
    assert asset.normalized_size_bytes is not None

    with Image.open(storage_dir / asset.normalized_path) as normalized:
        assert normalized.format == "JPEG"
        assert max(normalized.size) <= 1024


def test_upload_endpoint_rejects_oversized_profile_audio_before_asset_processing(
    app_client, db_session, monkeypatch
) -> None:
    from app.api import assets as assets_api

    called = False

    def fail_if_processed(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("oversized upload should be rejected before asset processing")

    monkeypatch.setattr(assets_api.settings, "profile_audio_max_bytes", 4)
    monkeypatch.setattr(assets_api, "save_profile_audio_asset", fail_if_processed)

    response = app_client.post(
        "/api/assets/profile-audio",
        files={"file": ("large.mp3", b"12345", "audio/mpeg")},
    )

    assert response.status_code == 413
    assert response.json()["error_code"] == "UPLOAD_TOO_LARGE"
    assert response.json()["message"] == "uploaded file is too large"
    assert called is False


def test_profile_audio_upload_rejects_ogg_voice_note_format(db_session, storage_dir) -> None:
    with pytest.raises(ValueError, match="profile audio must be MP3 or M4A"):
        save_profile_audio_asset(
            db_session,
            filename="voice-note.ogg",
            content=b"OggS" + b"\x00" * 128,
            storage_root=storage_dir,
            max_bytes=1024,
        )


def test_upload_endpoint_returns_specific_profile_audio_format_error(
    app_client, db_session
) -> None:
    response = app_client.post(
        "/api/assets/profile-audio",
        files={"file": ("voice-note.ogg", b"OggS" + b"\x00" * 128, "audio/ogg")},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "PROFILE_AUDIO_UNSUPPORTED_FORMAT"


def test_story_video_upload_endpoint_streams_to_temp_file(app_client, monkeypatch) -> None:
    from app.api import assets as assets_api

    captured: dict[str, bytes] = {}

    def fake_save_story_video_asset_from_path(*args, source_path, **kwargs):
        captured["content"] = source_path.read_bytes()
        return {
            "id": "asset-video-1",
            "kind": "story_video",
            "source_path": "assets/asset-video-1/source/original.mp4",
            "normalized_path": "assets/asset-video-1/normalized/story_video.mp4",
            "storage_backend": "local",
            "content_hash": "a" * 64,
            "mime": "video/mp4",
            "status": "normalized",
            "created_at": datetime.now(UTC),
        }

    monkeypatch.setattr(
        assets_api,
        "save_story_video_asset_from_path",
        fake_save_story_video_asset_from_path,
        raising=False,
    )

    response = app_client.post(
        "/api/assets/story-video",
        files={"file": ("story.mp4", b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16, "video/mp4")},
    )

    assert response.status_code == 201
    assert captured["content"].startswith(b"\x00\x00\x00\x18ftyp")
