from __future__ import annotations

import random
from typing import Any


def compute_typing_duration(
    text_length: int,
    *,
    personality_seed: dict[str, Any] | None,
    rng: random.Random,
) -> float:
    seed = personality_seed or {}
    chars_per_second = _positive_float(
        seed.get("typing_speed_cps"),
        default=rng.uniform(5.0, 7.5),
    )
    base = max(0, text_length) / chars_per_second
    jitter = base * rng.uniform(-0.3, 0.3)
    return max(2.0, min(15.0, base + jitter))


def _positive_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
<<<<<<< HEAD
    except TypeError, ValueError:
=======
    except (TypeError, ValueError):  # fmt: skip
>>>>>>> origin/main
        return default
    return parsed if parsed > 0 else default


__all__ = ["compute_typing_duration"]
