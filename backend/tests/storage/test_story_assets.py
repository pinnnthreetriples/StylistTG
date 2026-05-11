from app.config import Settings
from app.models import Asset
from app.services.assets import save_story_video_asset


def test_story_video_upload_rejects_filename_only_mime_spoof(db_session, storage_dir) -> None:
    try:
        save_story_video_asset(
            db_session,
            filename="not-video.mp4",
            content=b"this is not a video",
            storage_root=storage_dir,
            max_bytes=1024,
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "uploaded file is not a supported story video"


def test_story_video_upload_accepts_mp4_signature_when_preparation_succeeds(db_session, storage_dir, monkeypatch) -> None:
    monkeypatch.setattr("app.services.assets._prepare_story_video", lambda source_path, normalized_dir, config: source_path)
    asset = save_story_video_asset(
        db_session,
        filename="story.mp4",
        content=b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16,
        storage_root=storage_dir,
        max_bytes=1024,
    )

    assert asset.kind == "story_video"
    assert asset.mime == "video/mp4"


def test_story_video_upload_rejects_when_media_tools_are_missing(db_session, storage_dir) -> None:
    content = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16

    try:
        save_story_video_asset(
            db_session,
            filename="story.mp4",
            content=content,
            storage_root=storage_dir,
            max_bytes=1024,
            config=Settings(ffprobe_path="missing-ffprobe-for-test", ffmpeg_path="missing-ffmpeg-for-test"),
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "story video preparation requires ffprobe and ffmpeg"
    assert not any((storage_dir / "assets").iterdir())
    assert db_session.query(Asset).count() == 0


def test_story_video_upload_cleans_new_asset_dir_when_preparation_fails(db_session, storage_dir, monkeypatch) -> None:
    def fail_prepare(source_path, normalized_dir, config):
        raise ValueError("ffmpeg failed")

    monkeypatch.setattr("app.services.assets._prepare_story_video", fail_prepare)

    try:
        save_story_video_asset(
            db_session,
            filename="story.mp4",
            content=b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16,
            storage_root=storage_dir,
            max_bytes=1024,
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "ffmpeg failed"
    assert not any((storage_dir / "assets").iterdir())
    assert db_session.query(Asset).count() == 0
