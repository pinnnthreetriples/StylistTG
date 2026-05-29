"""Compatibility wrapper.

Canonical owner: app.modules.account_safety.terminal_status
Do not add new behavior here.
"""

from __future__ import annotations

from app.modules.account_safety.terminal_status import (
    TerminalStatusAlreadyNone,
    TerminalStatusClearResult,
    TerminalStatusColumnUnavailable,
    clear_terminal_status,
)

__all__ = [
    "TerminalStatusAlreadyNone",
    "TerminalStatusClearResult",
    "TerminalStatusColumnUnavailable",
    "clear_terminal_status",
]
