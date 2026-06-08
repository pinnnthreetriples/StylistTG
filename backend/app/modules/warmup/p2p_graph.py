from __future__ import annotations

import hashlib
import random
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, WarmupP2pFriendLink, WarmupTrustedPeer, new_id, utc_now


def assign_friends(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    k: int = 3,
    rng: random.Random | None = None,
    now: datetime | None = None,
) -> list[str]:
    existing = get_friends(session, account_id=account_id, workspace_id=workspace_id)
    if existing:
        return existing

    candidates = _eligible_friend_candidates(
        session,
        account_id=account_id,
        workspace_id=workspace_id,
    )
    if not candidates:
        return []

    active_rng = rng or _deterministic_rng(workspace_id, account_id)
    timestamp = now or utc_now()
    chosen = active_rng.sample(candidates, k=min(max(k, 0), len(candidates)))
    for friend_account_id in chosen:
        _add_link(
            session,
            workspace_id=workspace_id,
            account_id=account_id,
            friend_account_id=friend_account_id,
            now=timestamp,
        )
        if active_rng.random() < 0.5:
            _add_link(
                session,
                workspace_id=workspace_id,
                account_id=friend_account_id,
                friend_account_id=account_id,
                now=timestamp,
            )
    session.flush()
    return chosen


def get_friends(session: Session, *, account_id: str, workspace_id: str) -> list[str]:
    return list(
        session.scalars(
            select(WarmupP2pFriendLink.friend_account_id)
            .where(
                WarmupP2pFriendLink.workspace_id == workspace_id,
                WarmupP2pFriendLink.account_id == account_id,
            )
            .order_by(WarmupP2pFriendLink.created_at.asc(), WarmupP2pFriendLink.id.asc())
        )
    )


def touch_friend_interaction(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    friend_account_id: str,
    now: datetime | None = None,
) -> None:
    timestamp = now or utc_now()
    rows = session.scalars(
        select(WarmupP2pFriendLink).where(
            WarmupP2pFriendLink.workspace_id == workspace_id,
            (
                (WarmupP2pFriendLink.account_id == account_id)
                & (WarmupP2pFriendLink.friend_account_id == friend_account_id)
            )
            | (
                (WarmupP2pFriendLink.account_id == friend_account_id)
                & (WarmupP2pFriendLink.friend_account_id == account_id)
            ),
        )
    )
    for row in rows:
        row.last_interaction_at = timestamp


def _eligible_friend_candidates(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
) -> list[str]:
    rows = session.scalars(
        select(Account.id)
        .join(WarmupTrustedPeer, WarmupTrustedPeer.account_id == Account.id)
        .where(
            Account.workspace_id == workspace_id,
            Account.id != account_id,
            Account.telegram_user_id.is_not(None),
            WarmupTrustedPeer.workspace_id == workspace_id,
            WarmupTrustedPeer.revoked_at.is_(None),
            WarmupTrustedPeer.current_contacts < WarmupTrustedPeer.max_active_contacts,
        )
        .order_by(WarmupTrustedPeer.created_at.asc())
        .limit(100)
    ).all()
    return list(dict.fromkeys(rows))


def _add_link(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    friend_account_id: str,
    now: datetime,
) -> None:
    if account_id == friend_account_id:
        return
    exists = session.scalar(
        select(WarmupP2pFriendLink.id).where(
            WarmupP2pFriendLink.workspace_id == workspace_id,
            WarmupP2pFriendLink.account_id == account_id,
            WarmupP2pFriendLink.friend_account_id == friend_account_id,
        )
    )
    if exists is not None:
        return
    session.add(
        WarmupP2pFriendLink(
            id=new_id(),
            workspace_id=workspace_id,
            account_id=account_id,
            friend_account_id=friend_account_id,
            created_at=now,
        )
    )


def _deterministic_rng(workspace_id: str, account_id: str) -> random.Random:
    seed = hashlib.sha256(f"{workspace_id}:{account_id}".encode("utf-8")).hexdigest()
    return random.Random(int(seed[:16], 16))


__all__ = ["assign_friends", "get_friends", "touch_friend_interaction"]
