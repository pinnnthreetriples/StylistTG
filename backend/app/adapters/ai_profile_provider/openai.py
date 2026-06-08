from __future__ import annotations

import base64
from collections.abc import Callable
import time
from typing import Any

import httpx
from pydantic import SecretStr

from app.adapters.ai_profile_provider.base import (
    AIProfileProviderError,
    AvatarGenerationRequest,
    BioGenerationRequest,
    GeneratedAvatar,
    GeneratedBio,
)
from app.config import Settings


class OpenAIProfileProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        settings: Settings,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self._client = client
        self._sleep = sleep

    def generate_bio(self, request: BioGenerationRequest) -> GeneratedBio:
        api_key = _secret_value(self._settings.ai_profile_openai_api_key)
        if not self._settings.ai_profile_live_enabled or not api_key:
            raise AIProfileProviderError(
                "AI_PROFILE_PROVIDER_NOT_CONFIGURED",
                "AI profile provider is not configured",
            )
        payload = {
            "model": self._settings.ai_profile_openai_model,
            "messages": [
                {
                    "role": "system",
                    "content": "Write one short safe Telegram bio. No links. No claims.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Language: {request.language}\n"
                        f"Persona hints: {request.persona_hints}\n"
                        f"Variant: {request.attempt}"
                    ),
                },
            ],
            "temperature": 0.8,
            "max_tokens": 80,
        }
        response = self._post("/v1/chat/completions", payload, api_key)
        try:
            text = response["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise AIProfileProviderError(
                "AI_PROFILE_PROVIDER_BAD_RESPONSE",
                "AI profile provider returned an invalid response",
            ) from exc
        if not text:
            raise AIProfileProviderError(
                "AI_PROFILE_EMPTY_RESPONSE", "AI profile provider returned empty text"
            )
        return GeneratedBio(
            text=text[:120],
            provider=self.provider_name,
            model=self._settings.ai_profile_openai_model,
        )

    def generate_avatar(self, request: AvatarGenerationRequest) -> GeneratedAvatar:
        api_key = _secret_value(self._settings.ai_profile_openai_api_key)
        if not self._settings.ai_profile_live_enabled or not api_key:
            raise AIProfileProviderError(
                "AI_PROFILE_PROVIDER_NOT_CONFIGURED",
                "AI profile provider is not configured",
            )
        payload = {
            "model": self._settings.ai_profile_openai_image_model,
            "prompt": (
                "Square Telegram profile avatar, clean human-friendly abstract portrait, "
                f"persona hints: {request.persona_hints}, variant {request.attempt}"
            ),
            "size": "1024x1024",
            "n": 1,
            "response_format": "b64_json",
        }
        response = self._post("/v1/images/generations", payload, api_key)
        try:
            encoded = response["data"][0]["b64_json"]
            content = base64.b64decode(encoded)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AIProfileProviderError(
                "AI_PROFILE_PROVIDER_BAD_RESPONSE",
                "AI profile provider returned an invalid response",
            ) from exc
        return GeneratedAvatar(
            content=content,
            provider=self.provider_name,
            model=self._settings.ai_profile_openai_image_model,
        )

    def _post(self, path: str, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
        attempts = self._settings.ai_profile_max_retries + 1
        own_client = self._client is None
        client = self._client or httpx.Client(timeout=self._settings.ai_profile_timeout_seconds)
        url = f"{self._settings.ai_profile_openai_base_url.rstrip('/')}{path}"
        try:
            for attempt in range(attempts):
                try:
                    response = client.post(
                        url,
                        json=payload,
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                except httpx.TimeoutException as exc:
                    if attempt < attempts - 1:
                        self._sleep(0.1 * (2**attempt))
                        continue
                    raise AIProfileProviderError(
                        "AI_PROFILE_PROVIDER_TIMEOUT",
                        "AI profile provider request timed out",
                    ) from exc
                except httpx.HTTPError as exc:
                    if attempt < attempts - 1:
                        self._sleep(0.1 * (2**attempt))
                        continue
                    raise AIProfileProviderError(
                        "AI_PROFILE_PROVIDER_REQUEST_FAILED",
                        "AI profile provider request failed",
                    ) from exc
                if response.status_code in {429, 500, 502, 503, 504} and attempt < attempts - 1:
                    self._sleep(0.1 * (2**attempt))
                    continue
                if response.status_code == 429:
                    raise AIProfileProviderError(
                        "AI_PROFILE_PROVIDER_RATE_LIMITED",
                        "AI profile provider rate limited the request",
                    )
                if response.status_code >= 400:
                    raise AIProfileProviderError(
                        "AI_PROFILE_PROVIDER_REQUEST_FAILED",
                        "AI profile provider request failed",
                    )
                return response.json()
        finally:
            if own_client:
                client.close()
        raise AIProfileProviderError(
            "AI_PROFILE_PROVIDER_REQUEST_FAILED",
            "AI profile provider request failed",
        )


def _secret_value(value: SecretStr | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    return str(value)
