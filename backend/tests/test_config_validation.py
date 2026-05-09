"""Config validation tests for production/cloud safety.

Complements test_saas_foundation.py with additional edge cases:
S3 storage requirements, Fernet key shape, and TDLIB_STORAGE_BACKEND.
"""
from __future__ import annotations

import pytest

from app.config import Settings


# ---------------------------------------------------------------------------
# S3 storage config
# ---------------------------------------------------------------------------


class TestS3StorageConfig:
    """STORAGE_BACKEND=s3 must require all S3 fields."""

    def test_s3_requires_endpoint_url(self):
        with pytest.raises(ValueError, match="STORAGE_S3_ENDPOINT_URL"):
            Settings(
                storage_backend="s3",
                storage_s3_bucket="bucket",
                storage_s3_access_key_id="key",
                storage_s3_secret_access_key="secret",
            )

    def test_s3_requires_bucket(self):
        with pytest.raises(ValueError, match="STORAGE_S3_BUCKET"):
            Settings(
                storage_backend="s3",
                storage_s3_endpoint_url="https://s3.example.com",
                storage_s3_access_key_id="key",
                storage_s3_secret_access_key="secret",
            )

    def test_s3_requires_access_key_id(self):
        with pytest.raises(ValueError, match="STORAGE_S3_ACCESS_KEY_ID"):
            Settings(
                storage_backend="s3",
                storage_s3_endpoint_url="https://s3.example.com",
                storage_s3_bucket="bucket",
                storage_s3_secret_access_key="secret",
            )

    def test_s3_requires_secret_access_key(self):
        with pytest.raises(ValueError, match="STORAGE_S3_SECRET_ACCESS_KEY"):
            Settings(
                storage_backend="s3",
                storage_s3_endpoint_url="https://s3.example.com",
                storage_s3_bucket="bucket",
                storage_s3_access_key_id="key",
            )

    def test_s3_valid_config_accepted(self):
        config = Settings(
            storage_backend="s3",
            storage_s3_endpoint_url="https://s3.example.com",
            storage_s3_bucket="bucket",
            storage_s3_access_key_id="key",
            storage_s3_secret_access_key="secret",
        )
        assert config.storage_backend == "s3"

    def test_s3_missing_multiple_fields_listed(self):
        with pytest.raises(ValueError, match="STORAGE_S3_ENDPOINT_URL.*STORAGE_S3_BUCKET|STORAGE_S3_BUCKET.*STORAGE_S3_ENDPOINT_URL"):
            Settings(
                storage_backend="s3",
                storage_s3_access_key_id="key",
                storage_s3_secret_access_key="secret",
            )


# ---------------------------------------------------------------------------
# Storage backend validation
# ---------------------------------------------------------------------------


class TestStorageBackendValidation:
    """STORAGE_BACKEND must be local or s3; TDLIB must be local."""

    def test_invalid_storage_backend_rejected(self):
        with pytest.raises(ValueError, match="STORAGE_BACKEND must be local or s3"):
            Settings(storage_backend="gcs")

    def test_tdlib_storage_backend_only_local(self):
        with pytest.raises(ValueError, match="TDLIB_STORAGE_BACKEND currently supports only local"):
            Settings(tdlib_storage_backend="s3")


# ---------------------------------------------------------------------------
# Cloud config edge cases
# ---------------------------------------------------------------------------


class TestCloudConfigEdgeCases:
    """Cloud/prod config edge cases not covered by test_saas_foundation.py."""

    def _cloud_base(self, **overrides):
        base = {
            "app_env": "production",
            "auth_mode": "supabase_jwt",
            "enforce_localhost_only": False,
            "cors_origins": "https://dashboard.example.com",
            "stale_job_reaper_enabled": False,
            "operator_api_token": "operator-token-value",
            "proxy_credentials_encryption_key": "test-fernet-key",
        }
        base.update(overrides)
        return base

    def test_neon_mode_triggers_cloud_validation(self):
        with pytest.raises(ValueError, match="AUTH_MODE=local is not allowed"):
            Settings(app_env="development", db_connection_mode="neon", auth_mode="local")

    def test_staging_env_triggers_cloud_validation_for_localhost(self):
        with pytest.raises(ValueError, match="cloud API requires"):
            Settings(
                app_env="staging",
                auth_mode="supabase_jwt",
                db_connection_mode="neon",
                enforce_localhost_only=True,
                cors_origins="https://dashboard.example.com",
                stale_job_reaper_enabled=False,
            )

    def test_cloud_rejects_stale_job_reaper_enabled(self):
        with pytest.raises(ValueError, match="STALE_JOB_REAPER_ENABLED"):
            Settings(**self._cloud_base(stale_job_reaper_enabled=True))

    def test_cloud_rejects_empty_cors(self):
        with pytest.raises(ValueError, match="cloud API requires"):
            Settings(**self._cloud_base(cors_origins=""))

    def test_cloud_rejects_wildcard_cors(self):
        with pytest.raises(ValueError, match="cloud API requires"):
            Settings(**self._cloud_base(cors_origins="*"))

    def test_valid_cloud_config_accepted(self):
        config = Settings(**self._cloud_base())
        assert config.app_env == "production"
        assert config.auth_mode == "supabase_jwt"
        assert config.enforce_localhost_only is False

    def test_test_env_does_not_trigger_cloud_validation(self):
        config = Settings(app_env="test", auth_mode="local")
        assert config.auth_mode == "local"
