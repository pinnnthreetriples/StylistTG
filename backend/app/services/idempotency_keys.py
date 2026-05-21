"""Attempt idempotency key generation and Redis reservation.

Provides deterministic random_id derivation from UUID keys for TDLib send-pipeline
at-least-once delivery with idempotent reconciliation.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, NamedTuple


class IdempotencyKey(NamedTuple):
    key: str  # UUID hex (36 chars with dashes)
    random_id_hash: int  # int64 for TDLib random_id


def generate(attempt_id: str) -> IdempotencyKey:
    """Generate a new idempotency key for an attempt.

    The random_id_hash is deterministic from the key for reconciliation.
    """
    key = str(uuid.uuid4())
    return IdempotencyKey(key=key, random_id_hash=derive_random_id(key))


def derive_random_id(key: str) -> int:
    """Derive a stable int64 random_id from an idempotency key."""
    digest = hashlib.sha256(key.encode()).digest()[:8]
    return int.from_bytes(digest, "big", signed=True)


def reserve_in_redis(
    redis: Any,
    *,
    key: str,
    attempt_id: str,
    ttl_seconds: int = 3600,
) -> bool:
    """SET attempt:idem:{key} = attempt_id NX EX ttl_seconds. Returns True if reserved."""
    result = redis.set(
        f"attempt:idem:{key}",
        attempt_id,
        nx=True,
        ex=ttl_seconds,
    )
    return bool(result)


def lookup_attempt_id(redis: Any, *, key: str) -> str | None:
    """GET attempt:idem:{key}. Returns attempt_id or None."""
    value = redis.get(f"attempt:idem:{key}")
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


class IdempotencyConflict(RuntimeError):
    """Raised when an idempotency key reservation fails (already reserved)."""


__all__ = [
    "IdempotencyConflict",
    "IdempotencyKey",
    "derive_random_id",
    "generate",
    "lookup_attempt_id",
    "reserve_in_redis",
]
