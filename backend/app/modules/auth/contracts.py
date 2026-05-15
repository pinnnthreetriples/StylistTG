from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class AuthRequestLike(Protocol):
    @property
    def headers(self) -> Mapping[str, str]: ...


__all__ = ["AuthRequestLike"]
