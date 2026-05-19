"""In-memory TDLib-runtime stand-ins for end-to-end safety pipeline tests.

Phase 0 Task 5 requires a contract-compatible runtime stub that does NOT
talk to TDLib but can drive the same observation/generation/send code path
as the production runtime. The production code already exposes:

  - ``FakeAICommentProvider`` (drop-in for AICommentProvider)
  - ``FakeTelegramPostObserver`` (drop-in for TelegramPostObserver)
  - ``FakeTelegramCommentSender`` (drop-in for TelegramCommentSender)

This module composes those fakes into a single object so tests can construct
the entire pipeline with one call, and adds error-injection helpers
(FloodWait / network errors) that the existing fakes do not expose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Sequence

from app.models import NeuroCommentTarget
from app.services.neuro_commenting.ai_comment_generator import (
    AICommentGenerationError,
    AICommentProvider,
    FakeAICommentProvider,
)
from app.services.neuro_commenting.sender_service import (
    FakeTelegramCommentSender,
    SentCommentResult,
    TelegramCommentSendError,
)
from app.services.neuro_commenting.tdlib_observer import (
    FakeTelegramPostObserver,
    ObservedTelegramPost,
    TargetMetadata,
)


@dataclass
class SeededObserver:
    """Convenience builder for FakeTelegramPostObserver.

    Tests pre-load posts and optional metadata. The metadata defaults to the
    target's own channel_id / discussion_chat_id so production code-paths
    that require both fields to be present can succeed without an extra
    refresh round-trip.
    """

    posts: list[ObservedTelegramPost] = field(default_factory=list)
    metadata: TargetMetadata | None = None

    def add_post(
        self,
        *,
        source_chat_id: str,
        source_message_id: str,
        post_text: str | None = None,
        media_summary: str | None = None,
        language: str | None = None,
    ) -> ObservedTelegramPost:
        post = ObservedTelegramPost(
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
            post_text=post_text,
            media_summary=media_summary,
            language=language,
        )
        self.posts.append(post)
        return post

    def build(self) -> FakeTelegramPostObserver:
        return FakeTelegramPostObserver(metadata=self.metadata, posts=list(self.posts))


@dataclass
class InjectableSender:
    """Drop-in sender that lets a test pre-configure the next outcome.

    Defaults to a SENT outcome with a deterministic telegram_message_id.
    A test can swap the outcome to a flood-wait or generic error to drive
    the failure path through ``SenderService``.
    """

    telegram_message_id: str = "fake-telegram-message-1"
    next_error: TelegramCommentSendError | None = None
    calls: int = 0

    def build(self) -> FakeTelegramCommentSender:
        return FakeTelegramCommentSender(
            telegram_message_id=self.telegram_message_id,
            error=self.next_error,
        )

    def succeed(self, *, telegram_message_id: str = "fake-telegram-message-1") -> None:
        self.telegram_message_id = telegram_message_id
        self.next_error = None

    def fail(self, *, error_code: str, message: str = "") -> None:
        self.next_error = TelegramCommentSendError(message or error_code, error_code=error_code)


@dataclass
class FloodAICommentProvider:
    """AI provider stub that always raises ``AICommentGenerationError``."""

    error_code: str = "AI_TIMEOUT"
    message: str = "fake provider rejected the request"
    provider_name: str = "fake"
    model_name: str = "fake-neuro-comment-v1"

    def generate_comment(self, prompt: object) -> object:
        _ = prompt
        raise AICommentGenerationError(self.error_code, self.message)


@dataclass
class FakeTdlibRuntime:
    """Composite runtime used by the Phase 0 E2E pipeline test.

    Constructs the observer, AI provider and sender fakes that drive the
    neuro-commenting jobs without touching real TDLib bindings. Tests can
    swap any component out via the dedicated builder methods.
    """

    observer: SeededObserver = field(default_factory=SeededObserver)
    sender: InjectableSender = field(default_factory=InjectableSender)
    ai_provider: AICommentProvider = field(default_factory=FakeAICommentProvider)

    def seed_metadata_from_target(self, target: NeuroCommentTarget) -> None:
        if self.observer.metadata is not None:
            return
        self.observer.metadata = TargetMetadata(
            channel_id=target.channel_id or target.channel_ref,
            discussion_chat_id=target.discussion_chat_id,
            title=target.title,
            username=target.username,
            status=target.status,
        )

    def seeded_posts(self) -> Sequence[ObservedTelegramPost]:
        return tuple(self.observer.posts)

    def succeed_send(self, *, telegram_message_id: str = "fake-telegram-message-1") -> None:
        self.sender.succeed(telegram_message_id=telegram_message_id)

    def force_send_error(self, *, error_code: str, message: str = "") -> None:
        self.sender.fail(error_code=error_code, message=message)

    def force_ai_failure(self, *, error_code: str = "AI_TIMEOUT") -> None:
        self.ai_provider = FloodAICommentProvider(error_code=error_code)

    def build_observer(self) -> FakeTelegramPostObserver:
        return self.observer.build()

    def build_sender(self) -> FakeTelegramCommentSender:
        return self.sender.build()


def fake_sent_result(*, telegram_message_id: str = "fake-telegram-message") -> SentCommentResult:
    return SentCommentResult(
        telegram_message_id=telegram_message_id,
        sent_at=datetime.now(UTC),
    )


__all__ = [
    "FakeTdlibRuntime",
    "FloodAICommentProvider",
    "InjectableSender",
    "SeededObserver",
    "fake_sent_result",
]
