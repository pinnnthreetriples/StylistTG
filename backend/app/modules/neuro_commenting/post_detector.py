from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib


@dataclass(frozen=True)
class PostMatchDecision:
    matched: bool
    matched_mode: str | None
    matched_keywords: list[str]
    reason: str | None = None


class PostDetector:
    def __init__(self, *, random_seed: str = "neuro-commenting") -> None:
        self._random_seed = random_seed

    @property
    def random_seed(self) -> str:
        return self._random_seed

    def match(
        self,
        *,
        mode: str,
        post_text: str | None,
        keywords: list[str],
        exclude_keywords: list[str],
    ) -> PostMatchDecision:
        normalized = (post_text or "").lower()
        excluded = [keyword for keyword in _normalize(exclude_keywords) if keyword in normalized]
        if excluded:
            return PostMatchDecision(False, None, [], "excluded_keyword")
        handler = _MODE_HANDLERS.get(mode)
        if handler is None:
            return PostMatchDecision(False, None, [], "unsupported_mode")
        return handler(self, normalized, post_text, keywords)


def _normalize(values: list[str]) -> list[str]:
    return [value.strip().lower() for value in values if value.strip()]


def _match_all_posts(
    _detector: PostDetector, _normalized: str, _post_text: str | None, _keywords: list[str]
) -> PostMatchDecision:
    return PostMatchDecision(True, "all_posts", [])


def _match_keyword(
    _detector: PostDetector, normalized: str, _post_text: str | None, keywords: list[str]
) -> PostMatchDecision:
    matched = [keyword for keyword in _normalize(keywords) if keyword in normalized]
    if matched:
        return PostMatchDecision(True, "keyword_match", matched)
    return PostMatchDecision(False, None, [], "keyword_not_matched")


def _match_random(
    detector: PostDetector, _normalized: str, post_text: str | None, _keywords: list[str]
) -> PostMatchDecision:
    digest = hashlib.sha256(f"{detector.random_seed}:{post_text or ''}".encode()).digest()
    matched = digest[0] < 128
    return PostMatchDecision(
        matched,
        "random_posts" if matched else None,
        [],
        None if matched else "random_gate_closed",
    )


def _match_semantic(
    _detector: PostDetector, _normalized: str, _post_text: str | None, _keywords: list[str]
) -> PostMatchDecision:
    return PostMatchDecision(False, None, [], "semantic_not_enabled")


_MODE_HANDLERS: dict[
    str, Callable[[PostDetector, str, str | None, list[str]], PostMatchDecision]
] = {
    "all_posts": _match_all_posts,
    "keyword_match": _match_keyword,
    "random_posts": _match_random,
    "semantic_match": _match_semantic,
}
