from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class BioGenerationRequest:
    workspace_id: str
    account_id: str
    language: str
    persona_hints: dict[str, str]
    attempt: int


@dataclass(frozen=True)
class AvatarGenerationRequest:
    workspace_id: str
    account_id: str
    persona_hints: dict[str, str]
    attempt: int


@dataclass(frozen=True)
class GeneratedBio:
    text: str
    provider: str
    model: str


@dataclass(frozen=True)
class GeneratedAvatar:
    content: bytes
    provider: str
    model: str
    mime: str = "image/png"


class AIProfileProviderError(RuntimeError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class AIProfileProvider(Protocol):
    def generate_bio(self, request: BioGenerationRequest) -> GeneratedBio: ...

    def generate_avatar(self, request: AvatarGenerationRequest) -> GeneratedAvatar: ...
