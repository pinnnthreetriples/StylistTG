from __future__ import annotations

import pytest

from app.config import Settings
from app.models import Asset
from app.services.asset_cleanup import cleanup_orphan_asset_directories
from app.storage import build_storage_service
from app.storage.errors import InvalidStorageKeyError
from app.storage.local import LocalStorageService
from app.storage.paths import normalize_storage_key, resolve_tdlib_account_dirs


def test_local_storage_save_open_exists_delete(tmp_path) -> None:
    storage = LocalStorageService(tmp_path)

    stored = storage.save_bytes("workspace-1/assets/a/source/file.txt", b"hello", content_type="text/plain")

    assert stored.key == "workspace-1/assets/a/source/file.txt"
    assert stored.size_bytes == 5
    assert storage.exists(stored.key)
    with storage.open_read(stored.key) as handle:
        assert handle.read() == b"hello"
    assert storage.delete(stored.key) is True
    assert storage.exists(stored.key) is False


def test_storage_key_normalization_rejects_traversal() -> None:
    assert normalize_storage_key("assets\\one\\file.jpg") == "assets/one/file.jpg"

    with pytest.raises(InvalidStorageKeyError):
        normalize_storage_key("../tdlib/database")

    with pytest.raises(InvalidStorageKeyError):
        normalize_storage_key("/absolute/path")

    with pytest.raises(InvalidStorageKeyError):
        normalize_storage_key("C:\\storage\\asset.jpg")

    with pytest.raises(InvalidStorageKeyError):
        normalize_storage_key("assets/./asset.jpg")


def test_storage_config_validation_s3_requires_required_envs() -> None:
    with pytest.raises(ValueError, match="STORAGE_BACKEND=s3 requires"):
        Settings(storage_backend="s3")


def test_s3_adapter_builds_with_complete_config() -> None:
    config = Settings(
        storage_backend="s3",
        storage_s3_endpoint_url="https://example.invalid",
        storage_s3_bucket="bucket",
        storage_s3_access_key_id="access",
        storage_s3_secret_access_key="secret",
    )
    storage = build_storage_service(config)

    assert storage.backend_name == "s3"


def test_s3_secret_is_masked_in_settings_repr() -> None:
    config = Settings(
        storage_backend="s3",
        storage_s3_endpoint_url="https://example.invalid",
        storage_s3_bucket="bucket",
        storage_s3_access_key_id="access",
        storage_s3_secret_access_key="super-secret",
    )

    assert "super-secret" not in repr(config)


def test_tdlib_account_dirs_reject_path_traversal(tmp_path) -> None:
    config = Settings(
        tdlib_database_root=tmp_path / "tdlib-db",
        tdlib_files_root=tmp_path / "tdlib-files",
    )

    dirs = resolve_tdlib_account_dirs(config, "account-1")
    assert dirs.database_directory == (tmp_path / "tdlib-db" / "account-1").resolve()
    assert dirs.files_directory == (tmp_path / "tdlib-files" / "account-1").resolve()

    with pytest.raises(InvalidStorageKeyError):
        resolve_tdlib_account_dirs(config, "../escape")


def test_asset_cleanup_dry_run_deletes_nothing(db_session, tmp_path) -> None:
    storage = LocalStorageService(tmp_path)
    storage.save_bytes("assets/orphan/source/file.txt", b"orphan")

    report = cleanup_orphan_asset_directories(db_session, storage, dry_run=True)

    assert report.deleted == ["assets/orphan"]
    assert storage.exists("assets/orphan/source/file.txt")


def test_asset_cleanup_deletes_only_unknown_asset_dirs(db_session, tmp_path) -> None:
    storage = LocalStorageService(tmp_path)
    known = Asset(
        id="known",
        kind="profile_photo",
        source_path="assets/known/source/file.jpg",
        normalized_path="assets/known/normalized/file.jpg",
        content_hash="hash",
        mime="image/jpeg",
        status="normalized",
    )
    db_session.add(known)
    db_session.commit()
    storage.save_bytes("assets/known/source/file.jpg", b"known")
    storage.save_bytes("assets/orphan/source/file.jpg", b"orphan")
    storage.save_bytes("tdlib/database/account/db.sqlite", b"session")

    report = cleanup_orphan_asset_directories(db_session, storage, dry_run=False)

    assert "assets/orphan" in report.deleted
    assert storage.exists("assets/known/source/file.jpg")
    assert storage.exists("tdlib/database/account/db.sqlite")
    assert not storage.exists("assets/orphan/source/file.jpg")


def test_asset_cleanup_max_delete_guard(db_session, tmp_path) -> None:
    storage = LocalStorageService(tmp_path)
    storage.save_bytes("assets/one/source/file.jpg", b"1")
    storage.save_bytes("assets/two/source/file.jpg", b"2")

    report = cleanup_orphan_asset_directories(db_session, storage, dry_run=False, max_delete_count=1)

    assert "max delete count exceeded" in report.errors
