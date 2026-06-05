from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Account, AccountLifecycleEvent, new_id
from app.modules.account_lifecycle.transitions import (
    AccountLifecycleState,
    is_transition_allowed,
    normalize_state,
)
from app.services.secret_redaction import redact_metadata

TRANSITION_EVENT_TYPE = "account.lifecycle.transition"


class InvalidTransitionError(ValueError):
    pass


def advance(
    session: Session,
    account: Account,
    *,
    to_state: AccountLifecycleState | str,
    now: datetime,
    reason: str,
    actor_user_id: str | None = None,
    manual: bool = False,
    metadata: dict[str, object] | None = None,
) -> AccountLifecycleEvent | None:
    source = normalize_state(account.lifecycle_state)
    target = normalize_state(to_state)
    if source == target:
        return None
    if not is_transition_allowed(source, target, manual=manual):
        raise InvalidTransitionError(f"invalid lifecycle transition: {source.value}->{target.value}")

    account.lifecycle_state = target.value
    account.lifecycle_updated_at = now
    event = AccountLifecycleEvent(
        id=new_id(),
        workspace_id=account.workspace_id,
        account_id=account.id,
        event_type=TRANSITION_EVENT_TYPE,
        actor_user_id=actor_user_id,
        request_id=None,
        from_state=source.value,
        to_state=target.value,
        reason=reason,
        payload_json=redact_metadata(metadata or {}),
        occurred_at=now,
        created_at=now,
    )
    session.add(event)
    session.flush()
    return event


__all__ = [
    "TRANSITION_EVENT_TYPE",
    "AccountLifecycleState",
    "InvalidTransitionError",
    "advance",
    "is_transition_allowed",
]
