from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


class TerminalStatusColumnUnavailable(RuntimeError):
    pass


class TerminalStatusAlreadyNone(ValueError):
    pass


@dataclass(frozen=True)
class TerminalStatusClearResult:
    account_id: str
    previous_terminal_status: str
    terminal_status: str


def clear_terminal_status(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    reason: str,
) -> TerminalStatusClearResult:
    if len(reason.strip()) < 10:
        raise ValueError("reason must be at least 10 characters")
    if not _account_has_terminal_status_column(session):
        raise TerminalStatusColumnUnavailable("account.terminal_status column is not available")

    previous_status = session.execute(
        text(
            "SELECT terminal_status FROM account "
            "WHERE id = :account_id AND workspace_id = :workspace_id"
        ),
        {"account_id": account_id, "workspace_id": workspace_id},
    ).scalar_one_or_none()
    if previous_status is None:
        raise LookupError(account_id)
    if str(previous_status) == "none":
        raise TerminalStatusAlreadyNone("terminal_status is already none")

    session.execute(
        text(
            "UPDATE account SET terminal_status = 'none' "
            "WHERE id = :account_id AND workspace_id = :workspace_id"
        ),
        {"account_id": account_id, "workspace_id": workspace_id},
    )
    session.flush()
    return TerminalStatusClearResult(
        account_id=account_id,
        previous_terminal_status=str(previous_status),
        terminal_status="none",
    )


def _account_has_terminal_status_column(session: Session) -> bool:
    bind = session.get_bind()
    columns = inspect(bind).get_columns("account")
    return any(column["name"] == "terminal_status" for column in columns)


__all__ = [
    "TerminalStatusAlreadyNone",
    "TerminalStatusClearResult",
    "TerminalStatusColumnUnavailable",
    "clear_terminal_status",
]
