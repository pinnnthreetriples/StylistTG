from __future__ import annotations

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
        if mode == "all_posts":
            return PostMatchDecision(True, "all_posts", [])
        if mode == "keyword_match":
            matched = [keyword for keyword in _normalize(keywords) if keyword in normalized]
            if matched:
                return PostMatchDecision(True, "keyword_match", matched)
            return PostMatchDecision(False, None, [], "keyword_not_matched")
        if mode == "random_posts":
            digest = hashlib.sha256(f"{self._random_seed}:{post_text or ''}".encode()).digest()
            matched = digest[0] < 128
            return PostMatchDecision(
                matched,
                "random_posts" if matched else None,
                [],
                None if matched else "random_gate_closed",
            )
        if mode == "semantic_match":
            return PostMatchDecision(False, None, [], "semantic_not_enabled")
        return PostMatchDecision(False, None, [], "unsupported_mode")


def _normalize(values: list[str]) -> list[str]:
    return [value.strip().lower() for value in values if value.strip()]
