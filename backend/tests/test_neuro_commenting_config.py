from __future__ import annotations

import pytest

from app.config import Settings


def test_fake_ai_provider_is_accepted_without_key() -> None:
    config = Settings(_env_file=None, neuro_comment_ai_provider="fake")

    assert config.neuro_comment_ai_provider == "fake"


def test_openai_compatible_provider_requires_base_url_and_api_key() -> None:
    with pytest.raises(ValueError, match="NEURO_COMMENT_AI_BASE_URL"):
        Settings(_env_file=None, neuro_comment_ai_provider="openai_compatible")


def test_openai_compatible_provider_is_accepted_with_required_settings() -> None:
    config = Settings(
        _env_file=None,
        neuro_comment_ai_provider="openai_compatible",
        neuro_comment_ai_base_url="https://api.example.test/v1",
        neuro_comment_ai_api_key="test-key",
    )

    assert config.neuro_comment_ai_provider == "openai_compatible"


def test_unknown_ai_provider_is_rejected() -> None:
    with pytest.raises(
        ValueError, match="NEURO_COMMENT_AI_PROVIDER must be fake or openai_compatible"
    ):
        Settings(_env_file=None, neuro_comment_ai_provider="unknown")


def _cloud_kwargs(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "_env_file": None,
        "app_env": "production",
        "enforce_localhost_only": False,
        "operator_api_token": "token-1",
        "cors_origins": "https://example.com",
        "stale_job_reaper_enabled": False,
        "queue_inline_fallback_enabled": False,
        "proxy_credentials_encryption_key": "A" * 43 + "=",
        "auth_mode": "supabase_jwt",
    }
    defaults.update(overrides)
    return defaults


def test_fake_ai_provider_rejected_in_cloud_mode() -> None:
    with pytest.raises(ValueError, match="NEURO_COMMENT_AI_PROVIDER!=fake"):
        Settings(**_cloud_kwargs(neuro_comment_ai_provider="fake"))


def test_fake_ai_provider_accepted_in_staging_cloud_mode() -> None:
    config = Settings(
        **_cloud_kwargs(app_env="staging", neuro_comment_ai_provider="fake")
    )

    assert config.neuro_comment_ai_provider == "fake"
    assert config.app_env == "staging"


def test_openai_provider_accepted_in_cloud_mode() -> None:
    config = Settings(
        **_cloud_kwargs(
            neuro_comment_ai_provider="openai_compatible",
            neuro_comment_ai_base_url="https://api.example.test/v1",
            neuro_comment_ai_api_key="cloud-key",
        )
    )

    assert config.neuro_comment_ai_provider == "openai_compatible"
    assert config.app_env == "production"
