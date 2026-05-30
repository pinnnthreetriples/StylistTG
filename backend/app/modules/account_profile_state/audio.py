from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AccountProfileAudioState, utc_now


def profile_audio_state_payload(state: AccountProfileAudioState | None) -> dict[str, Any] | None:
    if state is None:
        return None
    return {
        "telegram_file_id": state.telegram_file_id,
        "title": state.title,
        "performer": state.performer,
        "duration_seconds": state.duration_seconds,
        "mime": state.mime,
        "source_asset_id": state.source_asset_id,
    }


def upsert_profile_audio_state(
    session: Session,
    *,
    account_id: str,
    telegram_file_id: str | None,
    source_asset_id: str | None,
    title: str | None = None,
    performer: str | None = None,
    duration_seconds: int | None = None,
    mime: str | None = None,
    telegram_audio_id: str | None = None,
    raw_tdlib_json: dict[str, Any] | None = None,
) -> AccountProfileAudioState:
    state = session.get(AccountProfileAudioState, account_id)
    if state is None:
        state = AccountProfileAudioState(account_id=account_id)
        session.add(state)

    state.telegram_audio_id = telegram_audio_id
    state.telegram_file_id = telegram_file_id
    state.title = title
    state.performer = performer
    state.duration_seconds = duration_seconds
    state.mime = mime
    state.source_asset_id = source_asset_id
    state.raw_tdlib_json = raw_tdlib_json
    state.synced_at = utc_now()
    session.commit()
    session.refresh(state)
    return state


def clear_profile_audio_state(session: Session, *, account_id: str) -> None:
    state = session.get(AccountProfileAudioState, account_id)
    if state is None:
        return
    session.delete(state)
    session.commit()


__all__ = [
    "clear_profile_audio_state",
    "profile_audio_state_payload",
    "upsert_profile_audio_state",
]
