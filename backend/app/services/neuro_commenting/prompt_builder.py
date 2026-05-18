from __future__ import annotations

from dataclasses import dataclass

from app.models import NeuroCommentCampaign, NeuroCommentObservedPost


BASE_PROMPT = """Напиши короткий естественный комментарий к посту в Telegram.
Комментарий должен быть релевантным теме поста.
Не используй ссылки, рекламу, оскорбления и призывы купить.
Длина: до 120 символов.
Язык: как в исходном посте.
Верни только текст комментария."""


@dataclass(frozen=True)
class BuiltPrompt:
    system_prompt: str
    user_prompt: str
    prompt_version: int


class PromptBuilder:
    def build(
        self,
        *,
        campaign: NeuroCommentCampaign,
        observed_post: NeuroCommentObservedPost,
    ) -> BuiltPrompt:
        template = campaign.prompt_template or BASE_PROMPT
        system_prompt = campaign.system_prompt or BASE_PROMPT
        negative_prompt = campaign.negative_prompt or ""
        language = campaign.language_mode or observed_post.language or "auto"
        user_prompt = "\n".join(
            part
            for part in (
                template,
                f"Язык: {language}.",
                f"Пост: {observed_post.post_text or ''}",
                f"Негативные ограничения: {negative_prompt}" if negative_prompt else "",
                "Safety constraints: no links, no ads, no insults, no calls to buy.",
            )
            if part
        )
        return BuiltPrompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_version=campaign.prompt_version,
        )
