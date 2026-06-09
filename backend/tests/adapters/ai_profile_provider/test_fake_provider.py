from __future__ import annotations

from app.adapters.ai_profile_provider import (
    AvatarGenerationRequest,
    BioGenerationRequest,
    FakeAIProfileProvider,
)


def test_fake_provider_is_deterministic() -> None:
    provider = FakeAIProfileProvider()
    request = BioGenerationRequest(
        workspace_id="workspace-1",
        account_id="account-1",
        language="ru",
        persona_hints={"role": "SMM", "tone": "живой"},
        attempt=0,
    )

    first_result = provider.generate_bio(request)
    second_result = provider.generate_bio(request)
    assert first_result == second_result, "fake provider must be deterministic"


def test_fake_provider_generates_png_avatar() -> None:
    provider = FakeAIProfileProvider()
    avatar = provider.generate_avatar(
        AvatarGenerationRequest(
            workspace_id="workspace-1",
            account_id="account-1",
            persona_hints={"role": "SMM"},
            attempt=0,
        )
    )

    assert avatar.provider == "fake"
    assert avatar.mime == "image/png"
    assert avatar.content.startswith(b"\x89PNG")
