"""Warmup text generation provider interface.

Абстракция, через которую планер и P2P-движок получают тексты: био,
перефразирование шаблонов, P2P-сообщения для трастовых пиров, ответы
@SpamBot. Конкретные реализации (OpenAI/Anthropic) подключаются в
Фазе 4 отдельным PR; в Фазе 0a единственный провайдер — Mock.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TextVariationRequest:
    """Input для perevарианта одного текста.

    `seed` должен быть детерминированным хэшем, чтобы варианты были
    воспроизводимы между рестартами воркера.
    """

    template: str
    seed: str
    locale: str = "ru"
    max_length: int | None = None


@dataclass(frozen=True)
class TextVariationResult:
    rendered: str
    template: str
    seed: str
    provider: str
    diagnostic_tokens_used: int = 0


class WarmupTextProvider(Protocol):
    """Минимальный интерфейс провайдера. Каждая реализация гарантирует:

    - Детерминированность при одинаковом seed (требование Фазы 0a).
    - Отсутствие IO в конструкторе (можно создавать в горячем пути).
    - Логирование через существующий `redact_text` на уровне вызова.
    """

    provider_name: str

    def is_available(self) -> bool: ...

    def generate_bio(self, *, seed: str, locale: str = "ru") -> TextVariationResult: ...

    def rewrite_text(self, request: TextVariationRequest) -> TextVariationResult: ...

    def compose_p2p_message(self, request: TextVariationRequest) -> TextVariationResult: ...

    def compose_spam_bot_reply(self, request: TextVariationRequest) -> TextVariationResult: ...


_BIO_TEMPLATES_RU: Sequence[str] = (
    "Люблю чай по утрам и долгие пешие прогулки.",
    "Путешествую, когда получается, и читаю, когда не получается.",
    "Коллекционирую интересные истории и фотографии заката.",
    "Учусь каждый день чему-то новому.",
    "Просто человек, который любит тишину и хорошую музыку.",
)

_P2P_TEMPLATES_RU: Sequence[str] = (
    "Привет! Как дела?",
    "Слушай, ты видел новый фильм?",
    "Давно не разговаривали — как сам?",
    "Рад тебя видеть онлайн.",
    "Есть пара минут? Хотел спросить совета.",
)

_SPAM_BOT_REPLIES_RU: Sequence[str] = (
    "Я обычный человек, не рассылаю рекламу и не продаю услуги.",
    "Я не пишу незнакомым, просто общаюсь с друзьями.",
    "Извините, если что-то выглядит подозрительно. Я обычный пользователь.",
)


class MockWarmupTextProvider:
    """Детерминированный Mock-провайдер для локальных тестов и CI.

    Выбирает шаблон из фиксированного пула по seed'у; никаких внешних
    вызовов не делает.
    """

    provider_name = "mock"

    def is_available(self) -> bool:
        return True

    def generate_bio(self, *, seed: str, locale: str = "ru") -> TextVariationResult:
        template = _pick(_BIO_TEMPLATES_RU, seed + ":bio")
        return TextVariationResult(
            rendered=template,
            template=template,
            seed=seed,
            provider=self.provider_name,
        )

    def rewrite_text(self, request: TextVariationRequest) -> TextVariationResult:
        rendered = _apply_light_variation(request.template, request.seed)
        return TextVariationResult(
            rendered=rendered,
            template=request.template,
            seed=request.seed,
            provider=self.provider_name,
        )

    def compose_p2p_message(self, request: TextVariationRequest) -> TextVariationResult:
        # Если шаблон пустой — берём из пула.
        base = request.template.strip() or _pick(_P2P_TEMPLATES_RU, request.seed + ":p2p")
        rendered = _apply_light_variation(base, request.seed)
        return TextVariationResult(
            rendered=rendered,
            template=base,
            seed=request.seed,
            provider=self.provider_name,
        )

    def compose_spam_bot_reply(self, request: TextVariationRequest) -> TextVariationResult:
        base = request.template.strip() or _pick(_SPAM_BOT_REPLIES_RU, request.seed + ":spam_bot")
        return TextVariationResult(
            rendered=base,
            template=base,
            seed=request.seed,
            provider=self.provider_name,
        )


class UnavailableWarmupTextProvider:
    """Fallback если конфиг явно отключает провайдера.

    Все методы возвращают пустой рендер; вызывающая сторона должна
    сначала проверить `is_available()`.
    """

    provider_name = "unavailable"

    def is_available(self) -> bool:
        return False

    def _unavailable(self) -> TextVariationResult:
        return TextVariationResult(
            rendered="",
            template="",
            seed="",
            provider=self.provider_name,
        )

    def generate_bio(self, *, seed: str, locale: str = "ru") -> TextVariationResult:
        return self._unavailable()

    def rewrite_text(self, request: TextVariationRequest) -> TextVariationResult:
        return self._unavailable()

    def compose_p2p_message(self, request: TextVariationRequest) -> TextVariationResult:
        return self._unavailable()

    def compose_spam_bot_reply(self, request: TextVariationRequest) -> TextVariationResult:
        return self._unavailable()


def build_warmup_text_provider() -> WarmupTextProvider:
    """Factory.

    В Фазе 0a всегда возвращает Mock. В Фазе 4 появится ветка, читающая
    `WARMUP_LLM_PROVIDER` из `Settings` и выбирающая реальный адаптер.
    """
    return MockWarmupTextProvider()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pick(items: Sequence[str], seed: str) -> str:
    index = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(items)
    return items[index]


_END_PUNCT_RE = re.compile(r"[.!?…]+\s*$")


def _apply_light_variation(text: str, seed: str) -> str:
    """Deterministic light-level variation.

    Переставляет пунктуацию в конце, добавляет или убирает многоточие,
    опционально переставляет местами две первые короткие фразы. Ничего
    character-level (гомоглифы остаются для Фазы 4b).
    """
    normalized = text.strip()
    if not normalized:
        return normalized
    seed_hash = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16)
    variant = seed_hash % 4
    stripped = _END_PUNCT_RE.sub("", normalized)
    if variant == 0:
        return stripped + "."
    if variant == 1:
        return stripped + "…"
    if variant == 2:
        return stripped + "!"
    return stripped
