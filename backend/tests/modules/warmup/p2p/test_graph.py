from datetime import UTC, datetime, timedelta
import random

from app.models import DEFAULT_LOCAL_WORKSPACE_ID, WarmupP2pFriendLink, WarmupTrustedPeer, new_id
from app.modules.warmup.p2p import record_p2p_contact, select_eligible_peer
from app.modules.warmup.p2p_graph import assign_friends, get_friends
from tests.helpers.warmup import seed_warmup_account


NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def test_assign_friends_creates_three_links_idempotently(db_session) -> None:
    sender = seed_warmup_account(db_session, telegram_user_id="100")
    peers = [_seed_trusted_peer(db_session, telegram_user_id=str(200 + index)) for index in range(4)]

    first = assign_friends(
        db_session,
        account_id=sender.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        rng=random.Random(1),
        now=NOW,
    )
    second = assign_friends(
        db_session,
        account_id=sender.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        rng=random.Random(99),
        now=NOW + timedelta(minutes=1),
    )

    assert len(first) == 3
    assert set(first).issubset({peer.id for peer in peers})
    assert set(second) == set(first)
    assert set(get_friends(db_session, account_id=sender.id, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID)) == set(first)


def test_select_eligible_peer_returns_only_assigned_friends(db_session) -> None:
    sender = seed_warmup_account(db_session, telegram_user_id="100")
    friend = _seed_trusted_peer(db_session, telegram_user_id="201")
    non_friend = _seed_trusted_peer(db_session, telegram_user_id="202")
    _add_friend_link(db_session, sender.id, friend.id, last_interaction_at=None)

    selected = select_eligible_peer(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        sender_account_id=sender.id,
        now=NOW,
    )

    assert selected is not None
    assert selected.account_id == friend.id
    assert selected.account_id != non_friend.id


def test_select_eligible_peer_prefers_never_contacted_friend(db_session) -> None:
    sender = seed_warmup_account(db_session, telegram_user_id="100")
    contacted = _seed_trusted_peer(db_session, telegram_user_id="201")
    never_contacted = _seed_trusted_peer(db_session, telegram_user_id="202")
    _add_friend_link(
        db_session,
        sender.id,
        contacted.id,
        last_interaction_at=NOW - timedelta(hours=1),
    )
    _add_friend_link(db_session, sender.id, never_contacted.id, last_interaction_at=None)

    selected = select_eligible_peer(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        sender_account_id=sender.id,
        now=NOW,
    )

    assert selected is not None
    assert selected.account_id == never_contacted.id


def test_record_p2p_contact_updates_friend_last_interaction(db_session) -> None:
    sender = _seed_trusted_peer(db_session, telegram_user_id="100")
    friend = _seed_trusted_peer(db_session, telegram_user_id="201")
    _add_friend_link(db_session, sender.id, friend.id, last_interaction_at=None)

    record_p2p_contact(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        sender_account_id=sender.id,
        receiver_account_id=friend.id,
        now=NOW,
    )

    link = db_session.query(WarmupP2pFriendLink).filter_by(account_id=sender.id).one()
    assert link.last_interaction_at == NOW.replace(tzinfo=None)


def test_select_eligible_peer_returns_none_when_no_friends_available(db_session) -> None:
    sender = seed_warmup_account(db_session, telegram_user_id="100")

    selected = select_eligible_peer(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        sender_account_id=sender.id,
        now=NOW,
    )

    assert selected is None


def _seed_trusted_peer(db_session, *, telegram_user_id: str):
    account = seed_warmup_account(db_session, telegram_user_id=telegram_user_id)
    db_session.add(
        WarmupTrustedPeer(
            id=new_id(),
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            account_id=account.id,
            eligible_from=NOW - timedelta(days=1),
            max_active_contacts=3,
            current_contacts=0,
        )
    )
    db_session.commit()
    return account


def _add_friend_link(
    db_session,
    account_id: str,
    friend_account_id: str,
    *,
    last_interaction_at: datetime | None,
) -> None:
    db_session.add(
        WarmupP2pFriendLink(
            id=new_id(),
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            account_id=account_id,
            friend_account_id=friend_account_id,
            created_at=NOW,
            last_interaction_at=last_interaction_at,
        )
    )
    db_session.commit()
