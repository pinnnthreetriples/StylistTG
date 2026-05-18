from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, WithJsonSchema


def _uuid_string(value: str) -> str:
    return str(UUID(value))


UuidString = Annotated[
    str,
    AfterValidator(_uuid_string),
    WithJsonSchema({"type": "string", "format": "uuid"}),
]


__all__ = ["UuidString"]
