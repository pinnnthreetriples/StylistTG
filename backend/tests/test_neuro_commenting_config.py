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
