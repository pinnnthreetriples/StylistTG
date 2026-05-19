"""Phase 1 Task 8: built-in prompt presets for the neuro-commenting UI.

The presets are intentionally hardcoded so the dashboard wizard has a stable
catalogue without a new table or seed-data pipeline. Future iterations can
promote them to a workspace-scoped table when per-tenant customisation is
required.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class PromptPreset:
    id: str
    name: str
    language: str
    description: str
    system_prompt: str
    prompt_template: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
            "language": self.language,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "prompt_template": self.prompt_template,
        }


_PRESETS: tuple[PromptPreset, ...] = (
    PromptPreset(
        id="short_native_ru",
        name="Короткий нативный (RU)",
        language="ru",
        description="3–7 слов, без эмодзи, релевантно посту",
        system_prompt=(
            "Ты комментатор в Telegram. Пиши коротко и нативно, без эмодзи, "
            "без капса, без приветствий."
        ),
        prompt_template=(
            "Напиши короткий комментарий (3–7 слов) к посту канала. "
            "Комментарий должен звучать естественно и быть релевантным теме."
        ),
    ),
    PromptPreset(
        id="expert_opinion_ru",
        name="Мнение эксперта (RU)",
        language="ru",
        description="1–2 предложения, экспертная позиция",
        system_prompt=(
            "Ты эксперт в обсуждаемой теме. Пиши спокойно, без эмодзи, без "
            "маркетинговых клише."
        ),
        prompt_template=(
            "Сформулируй мнение эксперта (1–2 предложения) по теме поста. "
            "Опирайся на факты из поста."
        ),
    ),
    PromptPreset(
        id="question_to_author_ru",
        name="Вопрос автору (RU)",
        language="ru",
        description="Один уточняющий вопрос автору",
        system_prompt=(
            "Ты внимательный читатель. Задавай один конкретный уточняющий "
            "вопрос автору без оценочных суждений."
        ),
        prompt_template=(
            "Сформулируй один уточняющий вопрос автору поста. Без воды и без "
            "благодарностей."
        ),
    ),
    PromptPreset(
        id="emoji_reaction_ru",
        name="Эмодзи + короткая фраза (RU)",
        language="ru",
        description="1 эмодзи + 2–4 слова",
        system_prompt=(
            "Ты пишешь живые короткие реакции. Используй ровно один эмодзи в "
            "начале и пару слов."
        ),
        prompt_template=(
            "Напиши реакцию: один эмодзи и 2–4 слова. Без знаков препинания "
            "в конце."
        ),
    ),
    PromptPreset(
        id="short_native_en",
        name="Short native (EN)",
        language="en",
        description="3–7 words, no emoji, on-topic",
        system_prompt=(
            "You write short, native-sounding Telegram comments. No emoji, no "
            "greetings, no marketing tone."
        ),
        prompt_template=(
            "Write a short comment (3–7 words) on the channel post. Keep it "
            "natural and on-topic."
        ),
    ),
)


def list_prompt_presets() -> tuple[PromptPreset, ...]:
    return _PRESETS


def get_prompt_preset(preset_id: str) -> PromptPreset | None:
    for preset in _PRESETS:
        if preset.id == preset_id:
            return preset
    return None


def iter_prompt_presets() -> Iterator[PromptPreset]:
    return iter(_PRESETS)


__all__ = [
    "PromptPreset",
    "get_prompt_preset",
    "iter_prompt_presets",
    "list_prompt_presets",
]
