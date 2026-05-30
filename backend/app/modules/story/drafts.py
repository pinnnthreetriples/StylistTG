from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountStoryDraft, AccountStoryPost, AssetKind, AssetStatus, utc_now
from app.modules.account_shared.interfaces import lookup_account
from app.services.assets import get_asset


def create_story_draft(
    session: Session, payload: dict[str, Any], *, workspace_id: str | None = None
) -> AccountStoryDraft:
    account = lookup_account(session, payload["account_id"], workspace_id=workspace_id)
    if account is None:
        raise ValueError("account not found")
    _validate_payload(session, payload, workspace_id=account.workspace_id)
    draft = AccountStoryDraft(
        account_id=payload["account_id"],
        asset_id=payload["asset_id"],
        media_kind=payload["media_kind"],
        caption=payload.get("caption"),
        privacy_preset=payload.get("privacy_preset") or "contacts",
        active_period_seconds=payload.get("active_period_seconds") or 86400,
        protect_content=bool(payload.get("protect_content")),
        validation_status="ready",
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return draft


def update_story_draft(
    session: Session,
    draft_id: str,
    payload: dict[str, Any],
    *,
    workspace_id: str | None = None,
) -> AccountStoryDraft:
    draft = _get_story_draft(session, draft_id, workspace_id=workspace_id)
    if draft is None:
        raise ValueError("story draft not found")
    next_payload: dict[str, Any] = {
        "account_id": draft.account_id,
        "asset_id": draft.asset_id,
        "media_kind": draft.media_kind,
        "caption": payload.get("caption", draft.caption),
        "privacy_preset": payload.get("privacy_preset", draft.privacy_preset),
        "active_period_seconds": payload.get("active_period_seconds", draft.active_period_seconds),
        "protect_content": payload.get("protect_content", draft.protect_content),
    }
    _validate_payload(session, next_payload, workspace_id=draft.account.workspace_id)
    draft.caption = next_payload["caption"]
    draft.privacy_preset = next_payload["privacy_preset"]
    draft.active_period_seconds = next_payload["active_period_seconds"]
    draft.protect_content = bool(next_payload["protect_content"])
    draft.updated_at = utc_now()
    session.commit()
    session.refresh(draft)
    return draft


def delete_story_draft(session: Session, draft_id: str, *, workspace_id: str | None = None) -> None:
    draft = _get_story_draft(session, draft_id, workspace_id=workspace_id)
    if draft is None:
        raise ValueError("story draft not found")
    asset_id = draft.asset_id
    asset_workspace_id = draft.account.workspace_id
    session.delete(draft)
    session.commit()
    _mark_orphan_story_asset(session, asset_id, workspace_id=asset_workspace_id)


def delete_story_drafts_for_asset(session: Session, *, account_id: str, asset_id: str) -> None:
    drafts = list(
        session.execute(
            select(AccountStoryDraft)
            .where(AccountStoryDraft.account_id == account_id)
            .where(AccountStoryDraft.asset_id == asset_id)
        )
        .scalars()
        .all()
    )
    if not drafts:
        return
    for draft in drafts:
        session.delete(draft)
    session.commit()


def list_story_drafts(
    session: Session, account_id: str, *, workspace_id: str | None = None
) -> list[AccountStoryDraft]:
    if lookup_account(session, account_id, workspace_id=workspace_id) is None:
        raise ValueError("account not found")
    statement = (
        select(AccountStoryDraft)
        .where(AccountStoryDraft.account_id == account_id)
        .order_by(AccountStoryDraft.created_at.asc())
    )
    if workspace_id is not None:
        statement = statement.join(Account, Account.id == AccountStoryDraft.account_id).where(
            Account.workspace_id == workspace_id
        )
    return list(session.execute(statement).scalars().all())


def _validate_payload(
    session: Session, payload: dict[str, Any], *, workspace_id: str | None = None
) -> None:
    media_kind = payload.get("media_kind")
    if media_kind not in {"image", "video"}:
        raise ValueError("unsupported story media_kind")
    caption = payload.get("caption")
    if caption and len(caption) > 1024:
        raise ValueError("story caption is too long")
    if payload.get("privacy_preset") not in {"contacts", "close_friends", "public"}:
        raise ValueError("unsupported story privacy_preset")
    if payload.get("active_period_seconds") != 86400:
        raise ValueError("only 24h story active period is supported before live capability check")
    asset = get_asset(session, payload.get("asset_id"), workspace_id=workspace_id)
    if asset is None:
        raise ValueError("story asset not found")
    expected_kind = AssetKind.STORY_IMAGE if media_kind == "image" else AssetKind.STORY_VIDEO
    if asset.kind != expected_kind:
        raise ValueError(f"asset kind is not {expected_kind}")
    if asset.status != AssetStatus.NORMALIZED:
        raise ValueError("asset is not ready for story execution")


def _mark_orphan_story_asset(
    session: Session, asset_id: str, *, workspace_id: str | None = None
) -> None:
    asset = get_asset(session, asset_id, workspace_id=workspace_id)
    if asset is None or asset.kind not in {AssetKind.STORY_IMAGE, AssetKind.STORY_VIDEO}:
        return
    draft_statement = (
        select(AccountStoryDraft.id).where(AccountStoryDraft.asset_id == asset_id).limit(1)
    )
    post_statement = (
        select(AccountStoryPost.id).where(AccountStoryPost.asset_id == asset_id).limit(1)
    )
    if workspace_id is not None:
        draft_statement = draft_statement.join(
            Account, Account.id == AccountStoryDraft.account_id
        ).where(Account.workspace_id == workspace_id)
        post_statement = post_statement.join(
            Account, Account.id == AccountStoryPost.account_id
        ).where(Account.workspace_id == workspace_id)
    draft_ref = session.execute(draft_statement).scalars().first()
    post_ref = session.execute(post_statement).scalars().first()
    if draft_ref or post_ref:
        return
    asset.status = AssetStatus.ORPHANED
    session.commit()


def _get_story_draft(
    session: Session, draft_id: str, *, workspace_id: str | None = None
) -> AccountStoryDraft | None:
    statement = select(AccountStoryDraft).where(AccountStoryDraft.id == draft_id)
    if workspace_id is not None:
        statement = statement.join(Account, Account.id == AccountStoryDraft.account_id).where(
            Account.workspace_id == workspace_id
        )
    return session.execute(statement).scalars().first()


__all__ = [
    "create_story_draft",
    "delete_story_draft",
    "delete_story_drafts_for_asset",
    "list_story_drafts",
    "update_story_draft",
]
