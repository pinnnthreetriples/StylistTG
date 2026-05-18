from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.config import Settings, settings
from app.services.neuro_commenting.prompt_builder import BuiltPrompt


@dataclass(frozen=True)
class GeneratedCommentText:
    text: str
    provider: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class AICommentGenerationError(RuntimeError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class AICommentProvider(Protocol):
    def generate_comment(self, prompt: BuiltPrompt) -> GeneratedCommentText: ...


class FakeAICommentProvider:
    provider_name = "fake"
    model_name = "fake-neuro-comment-v1"

    def generate_comment(self, prompt: BuiltPrompt) -> GeneratedCommentText:
        source = prompt.user_prompt.strip().splitlines()
        post_line = next((line for line in source if line.startswith("Пост:")), "Пост:")
        post_text = post_line.removeprefix("Пост:").strip()
        rendered = "Интересная мысль, согласен." if post_text else "Спасибо за полезный пост."
        return GeneratedCommentText(
            text=rendered[:120],
            provider=self.provider_name,
            model=self.model_name,
        )


class AICommentGenerator:
    def __init__(self, provider: AICommentProvider | None = None) -> None:
        self._provider = provider or FakeAICommentProvider()

    def generate(self, prompt: BuiltPrompt) -> GeneratedCommentText:
        return self._provider.generate_comment(prompt)


def build_ai_comment_generator(config: Settings = settings) -> AICommentGenerator:
    provider = config.neuro_comment_ai_provider
    if provider == "fake":
        return AICommentGenerator(FakeAICommentProvider())
    if provider == "openai_compatible":
        from app.services.neuro_commenting.ai_provider_openai import (
            OpenAICompatibleCommentProvider,
        )

        return AICommentGenerator(OpenAICompatibleCommentProvider(settings=config))
    raise ValueError(f"unknown AI provider: {provider}")
