from __future__ import annotations

from io import BytesIO
from pathlib import Path
import hashlib

import pytest
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from botocore.stub import ANY, Stubber

from app.config import Settings
from app.models import Asset, AssetKind
from app.services.asset_storage import get_asset_signed_url
from app.services.assets import save_profile_audio_asset
from app.storage.errors import InvalidStorageKeyError, StorageObjectNotFoundError
from app.storage.s3_compatible import S3CompatibleStorageService


def _s3_storage() -> tuple[S3CompatibleStorageService, Stubber]:
    storage = S3CompatibleStorageService(
        endpoint_url="https://r2.example.invalid",
        bucket="stylisttg-assets",
        region="auto",
        access_key_id="access",
        secret_access_key="secret",
        force_path_style=True,
    )
    stubber = Stubber(storage.client)
    return storage, stubber


def test_s3_storage_save_read_stat_delete() -> None:
    storage, stubber = _s3_storage()
    content = b"hello"
    expected_put = {
        "Bucket": storage.bucket,
        "Key": "assets/a/source/file.txt",
        "Body": content,
        "Metadata": {"sha256": "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"},
        "ContentType": "text/plain",
    }
    stubber.add_response("put_object", {}, expected_put)
    stubber.add_response(
        "head_object",
        {
            "ContentLength": len(content),
            "ContentType": "text/plain",
            "Metadata": {"sha256": expected_put["Metadata"]["sha256"]},
            "ETag": '"etag"',
        },
        {"Bucket": storage.bucket, "Key": "assets/a/source/file.txt"},
    )
    stubber.add_response(
        "get_object",
        {"Body": StreamingBody(BytesIO(content), len(content))},
        {"Bucket": storage.bucket, "Key": "assets/a/source/file.txt"},
    )
    stubber.add_response(
        "head_object",
        {
            "ContentLength": len(content),
            "ContentType": "text/plain",
            "Metadata": {"sha256": expected_put["Metadata"]["sha256"]},
            "ETag": '"etag"',
        },
        {"Bucket": storage.bucket, "Key": "assets/a/source/file.txt"},
    )
    stubber.add_response(
        "head_object",
        {
            "ContentLength": len(content),
            "ContentType": "text/plain",
            "Metadata": {"sha256": expected_put["Metadata"]["sha256"]},
            "ETag": '"etag"',
        },
        {"Bucket": storage.bucket, "Key": "assets/a/source/file.txt"},
    )
    stubber.add_response(
        "delete_object",
        {},
        {"Bucket": storage.bucket, "Key": "assets/a/source/file.txt"},
    )

    with stubber:
        stored = storage.save_bytes("assets/a/source/file.txt", content, content_type="text/plain")
        assert stored.storage_backend == "s3"
        assert stored.checksum == expected_put["Metadata"]["sha256"]
        stat = storage.stat(stored.key)
        assert stat.size_bytes == len(content)
        assert storage.read_bytes(stored.key) == content
        assert storage.exists(stored.key) is True
        assert storage.delete(stored.key) is True


def test_s3_storage_signed_url() -> None:
    storage, stubber = _s3_storage()
    stubber.add_response(
        "head_object",
        {
            "ContentLength": 5,
            "ContentType": "text/plain",
            "Metadata": {
                "sha256": "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
            },
            "ETag": '"etag"',
        },
        {"Bucket": storage.bucket, "Key": "assets/a/source/file.txt"},
    )
    with stubber:
        signed_url = storage.get_signed_url("assets/a/source/file.txt", expires_seconds=60)
        assert "X-Amz-Signature=" in signed_url


def test_s3_storage_missing_object_maps_to_storage_not_found() -> None:
    storage, stubber = _s3_storage()
    stubber.add_client_error(
        "head_object",
        service_error_code="404",
        service_message="not found",
        http_status_code=404,
        expected_params={"Bucket": storage.bucket, "Key": "assets/missing.jpg"},
    )
    with stubber, pytest.raises(StorageObjectNotFoundError):
        storage.stat("assets/missing.jpg")


def test_s3_storage_rejects_path_traversal_before_client_call() -> None:
    storage, stubber = _s3_storage()
    with stubber, pytest.raises(InvalidStorageKeyError):
        storage.save_bytes("../secret", b"nope")


def test_s3_storage_rejects_signed_url_for_tdlib_session_key() -> None:
    storage, _ = _s3_storage()
    with pytest.raises(ValueError, match="TDLib session"):
        storage.get_signed_url("tdlib/database/account/db.sqlite")


def test_asset_signed_url_rejects_non_asset_key() -> None:
    storage, _ = _s3_storage()
    asset = Asset(
        id="asset-1",
        kind=AssetKind.PROFILE_PHOTO,
        source_path="assets/asset-1/source/original.jpg",
        normalized_path="sessions/not-an-asset.jpg",
        content_hash="hash",
        mime="image/jpeg",
        status="normalized",
    )

    with pytest.raises(InvalidStorageKeyError, match="application assets"):
        get_asset_signed_url(asset, storage=storage)


def test_s3_signed_url_for_missing_object_fails_cleanly() -> None:
    storage, stubber = _s3_storage()
    stubber.add_client_error(
        "head_object",
        service_error_code="404",
        service_message="not found",
        http_status_code=404,
        expected_params={"Bucket": storage.bucket, "Key": "assets/missing.jpg"},
    )
    with stubber, pytest.raises(StorageObjectNotFoundError):
        storage.get_signed_url("assets/missing.jpg")


def test_profile_audio_upload_populates_s3_metadata(db_session) -> None:
    storage, stubber = _s3_storage()
    content = b"ID3" + b"\0" * 32
    checksum = hashlib.sha256(content).hexdigest()
    stubber.add_response(
        "put_object",
        {},
        {
            "Bucket": storage.bucket,
            "Key": ANY,
            "Body": content,
            "Metadata": {"sha256": checksum},
            "ContentType": "audio/mpeg",
        },
    )
    stubber.add_response(
        "put_object",
        {},
        {
            "Bucket": storage.bucket,
            "Key": ANY,
            "Body": content,
            "Metadata": {"sha256": checksum},
            "ContentType": "audio/mpeg",
        },
    )
    with stubber:
        asset = save_profile_audio_asset(
            db_session,
            filename="song.mp3",
            content=content,
            storage_root=Path("unused"),
            max_bytes=1024,
            storage_service=storage,
        )

    assert asset.kind == AssetKind.PROFILE_AUDIO
    assert asset.storage_backend == "s3"
    assert asset.storage_bucket == storage.bucket
    assert asset.source_key and asset.source_key.startswith("assets/")
    assert asset.normalized_key and asset.normalized_key.startswith("assets/")
    assert asset.source_size_bytes == len(content)
    assert asset.normalized_size_bytes == len(content)
    assert asset.source_content_type == "audio/mpeg"
    assert asset.normalized_content_type == "audio/mpeg"
    assert asset.source_checksum == checksum
    assert asset.normalized_checksum == checksum


def test_s3_secret_not_exposed_in_settings_repr() -> None:
    config = Settings(
        storage_backend="s3",
        storage_s3_endpoint_url="https://r2.example.invalid",
        storage_s3_bucket="bucket",
        storage_s3_access_key_id="access",
        storage_s3_secret_access_key="very-secret",
    )

    assert "very-secret" not in repr(config)


def test_client_error_message_does_not_include_secret() -> None:
    storage, stubber = _s3_storage()
    stubber.add_client_error(
        "head_object",
        service_error_code="500",
        service_message="boom",
        http_status_code=500,
        expected_params={"Bucket": storage.bucket, "Key": "assets/file.txt"},
    )
    with stubber, pytest.raises(ClientError) as exc_info:
        storage.stat("assets/file.txt")
    assert "secret" not in str(exc_info.value)
