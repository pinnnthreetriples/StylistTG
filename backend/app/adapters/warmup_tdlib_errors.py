from __future__ import annotations

# pyright: reportUnusedFunction=false

import re
from typing import Any

from app.adapters.tdlib_auth import map_tdlib_error
from app.adapters.warmup_tdlib_contracts import WarmupActionResult


_FLOOD_WAIT_RE = re.compile(r"FLOOD_WAIT_(\d+)", re.IGNORECASE)


def _classify_tdlib_error(error: dict[str, Any], action_type: str) -> WarmupActionResult:
    message = str(error.get("message") or "TDLib error")
    upper = message.upper()
    flood_match = _FLOOD_WAIT_RE.search(upper)
    if flood_match:
        retry_after = int(flood_match.group(1))
        return WarmupActionResult(
            status="flood_wait",
            action_type=action_type,
            retry_after_seconds=retry_after,
            error_code="tdlib_flood_wait",
            error_class="rate_limit",
            metadata={"message": message, "retry_after_seconds": retry_after},
        )
    if any(token in upper for token in ("FROZEN", "DEACTIVATED", "AUTH_KEY", "USER_DEACTIVATED")):
        mapped = map_tdlib_error(error)
        return WarmupActionResult(
            status="runtime_broken",
            action_type=action_type,
            error_code=mapped.recovery_marker or "tdlib_runtime_broken",
            error_class="runtime",
            metadata={"message": message, "runtime_health": mapped.runtime_health},
        )
    return WarmupActionResult(
        status="network_error",
        action_type=action_type,
        error_code="tdlib_error",
        error_class="network",
        metadata={"message": message},
    )


class _AdapterClientError(Exception):
    def __init__(
        self,
        *,
        status: str,
        error_code: str,
        error_class: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.error_code = error_code
        self.error_class = error_class
        self.message = message

    def as_action_result(self, action_type: str) -> WarmupActionResult:
        return WarmupActionResult(
            status=self.status,
            action_type=action_type,
            error_code=self.error_code,
            error_class=self.error_class,
            metadata={"message": self.message},
        )

    @classmethod
    def from_tdlib_error(cls, event: dict[str, Any]) -> "_AdapterClientError":
        message = str(event.get("message") or "tdlib error")
        upper = message.upper()
        if "FLOOD" in upper:
            return cls(
                status="flood_wait",
                error_code="tdlib_flood_wait",
                error_class="rate_limit",
                message=message,
            )
        return cls(
            status="runtime_broken",
            error_code="tdlib_auth_error",
            error_class="auth_state",
            message=message,
        )
