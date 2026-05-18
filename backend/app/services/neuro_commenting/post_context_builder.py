from __future__ import annotations

from dataclasses import dataclass

from app.models import NeuroCommentObservedPost


@dataclass(frozen=True)
class PostContext:
    text: str
    media_summary: str | None
    language: str | None


class PostContextBuilder:
    def build(self, observed_post: NeuroCommentObservedPost) -> PostContext:
        return PostContext(
            text=observed_post.post_text or "",
            media_summary=observed_post.media_summary,
            language=observed_post.language,
        )
