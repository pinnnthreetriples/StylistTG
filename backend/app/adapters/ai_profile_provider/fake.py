from __future__ import annotations

import hashlib
from io import BytesIO

from PIL import Image, ImageDraw

from app.adapters.ai_profile_provider.base import (
    AvatarGenerationRequest,
    BioGenerationRequest,
    GeneratedAvatar,
    GeneratedBio,
)


class FakeAIProfileProvider:
    provider_name = "fake"
    bio_model = "fake-ai-profile-bio-v1"
    avatar_model = "fake-ai-profile-avatar-v1"

    def generate_bio(self, request: BioGenerationRequest) -> GeneratedBio:
        digest = _digest(request.workspace_id, request.account_id, request.attempt, request.persona_hints)
        tones = ["спокойный", "живой", "точный", "дружелюбный", "лаконичный"]
        roles = ["SMM", "контент", "дизайн", "маркетинг", "продажи"]
        tone = request.persona_hints.get("tone") or tones[int(digest[:2], 16) % len(tones)]
        role = request.persona_hints.get("role") or roles[int(digest[2:4], 16) % len(roles)]
        text = f"{tone.capitalize()} профиль про {role}. Пишу коротко, без шума."
        if request.language.lower().startswith("en"):
            text = f"{tone.capitalize()} {role} profile. Clear notes, no noise."
        return GeneratedBio(text=text[:120], provider=self.provider_name, model=self.bio_model)

    def generate_avatar(self, request: AvatarGenerationRequest) -> GeneratedAvatar:
        digest = _digest(request.workspace_id, request.account_id, request.attempt, request.persona_hints)
        rgb = tuple(int(digest[index : index + 2], 16) for index in (0, 2, 4))
        image = Image.new("RGB", (256, 256), rgb)
        draw = ImageDraw.Draw(image)
        accent = tuple(255 - channel for channel in rgb)
        draw.ellipse((52, 38, 204, 190), fill=accent)
        draw.rectangle((74, 176, 182, 220), fill=accent)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return GeneratedAvatar(
            content=buffer.getvalue(),
            provider=self.provider_name,
            model=self.avatar_model,
        )


def _digest(
    workspace_id: str,
    account_id: str,
    attempt: int,
    persona_hints: dict[str, str],
) -> str:
    material = "|".join(
        [
            workspace_id,
            account_id,
            str(attempt),
            ",".join(f"{key}={value}" for key, value in sorted(persona_hints.items())),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
