from app.config import Settings
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


def test_story_video_upload_accepts_mp4_signature(db_session, storage_dir) -> None:
    asset = save_story_video_asset(
        db_session,
        filename="story.mp4",
        content=b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16,
        storage_root=storage_dir,
        max_bytes=1024,
        config=Settings(ffprobe_path="missing-ffprobe-for-test", ffmpeg_path="missing-ffmpeg-for-test"),
    )

    assert asset.kind == "story_video"
    assert asset.mime == "video/mp4"


def test_story_video_upload_uses_pass_through_when_media_tools_are_missing(db_session, storage_dir) -> None:
    content = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16

    asset = save_story_video_asset(
        db_session,
        filename="story.mp4",
        content=content,
        storage_root=storage_dir,
        max_bytes=1024,
        config=Settings(ffprobe_path="missing-ffprobe-for-test", ffmpeg_path="missing-ffmpeg-for-test"),
    )

    assert (storage_dir / asset.normalized_path).read_bytes() == content
