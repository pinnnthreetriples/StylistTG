from __future__ import annotations

from app.config import Settings, settings


def build_ai_profile_provider(config: Settings = settings):
    provider = config.ai_profile_provider
    if provider == "fake":
        from app.adapters.ai_profile_provider.fake import FakeAIProfileProvider

        return FakeAIProfileProvider()
    if provider == "openai":
        from app.adapters.ai_profile_provider.openai import OpenAIProfileProvider

        return OpenAIProfileProvider(settings=config)
    if provider == "anthropic":
        from app.adapters.ai_profile_provider.anthropic import AnthropicProfileProvider

        return AnthropicProfileProvider(settings=config)
    raise ValueError(f"unknown AI profile provider: {provider}")
