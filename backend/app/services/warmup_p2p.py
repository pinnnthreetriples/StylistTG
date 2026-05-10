"""Phase 4 · trusted-peer pairing service.

Подбор peer'а для `p2p_send`-action и атомарная запись результата успешного
контакта. Используется из warmup_dispatch, изолировано от TDLib-адаптера —
адаптер только отправляет TDLib-запросы, а eligibility/cooldown логика
живёт здесь.

Eligibility-правила:
- peer должен быть в `WarmupTrustedPeer` workspace'а;
- `revoked_at IS NULL`;
- `eligible_from <= now`;
- `current_contacts < max_active_contacts`;
- peer.account_id != sender.account_id (не пишем сам себе);
- peer.account.telegram_user_id IS NOT NULL (нужно знать получателя);
- peer.account.workspace_id совпадает с sender.workspace_id.

Pairing — детерминированный по `created_at` ASC, чтобы тесты были
воспроизводимы и в проде между тиками peer'ы выбирались равномерно.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, WarmupTrustedPeer, utc_now


@dataclass(frozen=True)
class WarmupPeerCandidate:
    """Снимок eligible peer'а для p2p-сессии."""

    peer_row_id: str
    account_id: str
    telegram_user_id: str
    current_contacts: int
    max_active_contacts: int


def select_eligible_peer(
    session: Session,
    *,
    workspace_id: str,
    sender_account_id: str,
    now: datetime | None = None,
    exclude_account_ids: tuple[str, ...] = (),
) -> WarmupPeerCandidate | None:
    """Возвращает первого eligible peer'а в workspace или None.

    Не блокирует строки (no FOR UPDATE) — между тиками одного worker'а
    нет гонок, потому что dispatch tick одиночный per queue. Для
    multi-worker setup можно добавить advisory lock per workspace.
    """
    timestamp = now or utc_now()
    excluded = set(exclude_account_ids) | {sender_account_id}
    rows = session.execute(
        select(WarmupTrustedPeer, Account)
        .join(Account, Account.id == WarmupTrustedPeer.account_id)
        .where(
            WarmupTrustedPeer.workspace_id == workspace_id,
            WarmupTrustedPeer.revoked_at.is_(None),
            WarmupTrustedPeer.eligible_from <= timestamp,
            WarmupTrustedPeer.current_contacts < WarmupTrustedPeer.max_active_contacts,
            Account.workspace_id == workspace_id,
            Account.telegram_user_id.is_not(None),
        )
        .order_by(WarmupTrustedPeer.created_at.asc())
    ).all()
    for peer, account in rows:
        if account.id in excluded:
            continue
        return WarmupPeerCandidate(
            peer_row_id=peer.id,
            account_id=account.id,
            telegram_user_id=str(account.telegram_user_id),
            current_contacts=peer.current_contacts,
            max_active_contacts=peer.max_active_contacts,
        )
    return None


def record_p2p_contact(
    session: Session,
    *,
    workspace_id: str,
    sender_account_id: str,
    receiver_account_id: str,
    now: datetime | None = None,
) -> dict[str, int | None]:
    """Атомарно увеличивает `current_contacts` для receiver и (опц.) sender.

    Sender инкрементируется только если он сам числится в trusted pool —
    это валидно для двунаправленных контактов между двумя зрелыми
    аккаунтами. Если sender пока не в pool (типичный сценарий: учётка
    в процессе подготовки), его счётчик не трогаем.

    Возвращает словарь `{"sender_contacts": int|None, "receiver_contacts": int}`
    для аудита.
    """
    timestamp = now or utc_now()
    receiver = session.execute(
        select(WarmupTrustedPeer).where(
            WarmupTrustedPeer.workspace_id == workspace_id,
            WarmupTrustedPeer.account_id == receiver_account_id,
        )
    ).scalar_one_or_none()
    if receiver is None:
        raise ValueError("receiver is not in trusted-peer pool")
    receiver.current_contacts = receiver.current_contacts + 1
    receiver.updated_at = timestamp

    sender = session.execute(
        select(WarmupTrustedPeer).where(
            WarmupTrustedPeer.workspace_id == workspace_id,
            WarmupTrustedPeer.account_id == sender_account_id,
        )
    ).scalar_one_or_none()
    if sender is not None:
        sender.current_contacts = sender.current_contacts + 1
        sender.updated_at = timestamp

    session.flush()
    return {
        "receiver_contacts": receiver.current_contacts,
        "sender_contacts": sender.current_contacts if sender is not None else None,
    }
