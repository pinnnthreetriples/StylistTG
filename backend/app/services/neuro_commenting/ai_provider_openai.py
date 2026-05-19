from __future__ import annotations

from collections.abc import Callable
import time
from typing import Any, cast

import httpx
from pydantic import SecretStr

from app.config import Settings
from app.services.neuro_commenting.ai_comment_generator import (
    AICommentGenerationError,
    GeneratedCommentText,
)
from app.services.neuro_commenting.prompt_builder import BuiltPrompt


class OpenAICompatibleCommentProvider:
    provider_name = "openai_compatible"

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

    def generate_comment(self, prompt: BuiltPrompt) -> GeneratedCommentText:
        base_url = self._settings.neuro_comment_ai_base_url
        api_key = self._secret_value(self._settings.neuro_comment_ai_api_key)
        if not base_url or not api_key:
            raise AICommentGenerationError(
                "AI_PROVIDER_NOT_CONFIGURED", "AI provider is not configured"
            )
        payload = {
            "model": self._settings.neuro_comment_ai_model,
            "messages": [
                {"role": "system", "content": prompt.system_prompt},
                {"role": "user", "content": prompt.user_prompt},
            ],
            "temperature": self._settings.neuro_comment_ai_temperature,
            "max_tokens": self._settings.neuro_comment_ai_max_tokens,
        }
        url = f"{base_url.rstrip('/')}/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        attempts = self._settings.neuro_comment_ai_max_retries + 1
        own_client = self._client is None
        client = self._client or httpx.Client(
            timeout=self._settings.neuro_comment_ai_timeout_seconds
        )
        try:
            last_status: int | None = None
            for attempt in range(attempts):
                try:
                    response = client.post(url, json=payload, headers=headers)
                except httpx.TimeoutException as exc:
                    if attempt < attempts - 1:
                        self._sleep(0.1 * (2**attempt))
                        continue
                    raise AICommentGenerationError(
                        "AI_PROVIDER_TIMEOUT", "AI provider request timed out"
                    ) from exc
                except httpx.HTTPError as exc:
                    if attempt < attempts - 1:
                        self._sleep(0.1 * (2**attempt))
                        continue
                    raise AICommentGenerationError(
                        "AI_PROVIDER_REQUEST_FAILED", "AI provider request failed"
                    ) from exc

                last_status = response.status_code
                if response.status_code == 429 and attempt < attempts - 1:
                    self._sleep(0.1 * (2**attempt))
                    continue
                if response.status_code >= 500 and attempt < attempts - 1:
                    self._sleep(0.1 * (2**attempt))
                    continue
                if response.status_code == 429:
                    raise AICommentGenerationError(
                        "AI_PROVIDER_RATE_LIMITED", "AI provider rate limited the request"
                    )
                if response.status_code >= 500:
                    raise AICommentGenerationError(
                        "AI_PROVIDER_REQUEST_FAILED", "AI provider request failed"
                    )
                if response.status_code >= 400:
                    raise AICommentGenerationError(
                        "AI_PROVIDER_REQUEST_FAILED", "AI provider request failed"
                    )
                return self._parse_response(response)
            code = (
                "AI_PROVIDER_RATE_LIMITED" if last_status == 429 else "AI_PROVIDER_REQUEST_FAILED"
            )
            raise AICommentGenerationError(code, "AI provider request failed")
        finally:
            if own_client:
                client.close()

    def _parse_response(self, response: httpx.Response) -> GeneratedCommentText:
        try:
            payload = response.json()
            choices = payload["choices"]
            content = choices[0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AICommentGenerationError(
                "AI_PROVIDER_BAD_RESPONSE", "AI provider returned an invalid response"
            ) from exc
        if not isinstance(content, str):
            raise AICommentGenerationError(
                "AI_PROVIDER_BAD_RESPONSE", "AI provider returned an invalid response"
            )
        text = content.strip()
        if not text:
            raise AICommentGenerationError("AI_EMPTY_RESPONSE", "AI provider returned empty text")
        usage = cast(dict[str, Any], payload.get("usage") or {})
        return GeneratedCommentText(
            text=text,
            provider=self.provider_name,
            model=self._settings.neuro_comment_ai_model,
            prompt_tokens=self._int_or_none(usage.get("prompt_tokens")),
            completion_tokens=self._int_or_none(usage.get("completion_tokens")),
            total_tokens=self._int_or_none(usage.get("total_tokens")),
        )

    @staticmethod
    def _secret_value(value: SecretStr | str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, SecretStr):
            return value.get_secret_value()
        return str(value)

    @staticmethod
    def _int_or_none(value: object) -> int | None:
        return value if isinstance(value, int) else None
