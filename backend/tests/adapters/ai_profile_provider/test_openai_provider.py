from __future__ import annotations

import base64

import httpx
import pytest
from pydantic import SecretStr

from app.adapters.ai_profile_provider import AvatarGenerationRequest, BioGenerationRequest
from app.adapters.ai_profile_provider.openai import OpenAIProfileProvider
from app.config import Settings


def test_openai_provider_requires_live_gate_and_secret() -> None:
    with pytest.raises(ValueError, match="AI_PROFILE_LIVE_ENABLED"):
        Settings(ai_profile_provider="openai")


def test_openai_provider_parses_mocked_bio_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer sk-test"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Short bio"}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAIProfileProvider(
        settings=Settings(
            ai_profile_provider="openai",
            ai_profile_live_enabled=True,
            ai_profile_openai_api_key=SecretStr("sk-test"),
        ),
        client=client,
        sleep=lambda _seconds: None,
    )

    result = provider.generate_bio(
        BioGenerationRequest(
            workspace_id="workspace-1",
            account_id="account-1",
            language="en",
            persona_hints={},
            attempt=0,
        )
    )

    assert result.text == "Short bio"
    assert result.provider == "openai"


def test_openai_provider_parses_mocked_avatar_response() -> None:
    encoded = base64.b64encode(b"image-bytes").decode("ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/images/generations"
        return httpx.Response(200, json={"data": [{"b64_json": encoded}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAIProfileProvider(
        settings=Settings(
            ai_profile_provider="openai",
            ai_profile_live_enabled=True,
            ai_profile_openai_api_key=SecretStr("sk-test"),
        ),
        client=client,
        sleep=lambda _seconds: None,
    )

    result = provider.generate_avatar(
        AvatarGenerationRequest(
            workspace_id="workspace-1",
            account_id="account-1",
            persona_hints={},
            attempt=0,
        )
    )

    assert result.content == b"image-bytes"
    assert result.provider == "openai"
