from __future__ import annotations

# pyright: reportUnusedFunction=false

import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.adapters.warmup_text_provider import TextVariationRequest, WarmupTextProvider
from app.models import WarmupSession, WarmupStatus
from app.modules.warmup.channel_state.contracts import ChannelStateSnapshot
from app.modules.warmup.channel_state.repository import get_states_for_account
from app.modules.warmup.events import write_warmup_event
from app.modules.warmup.p2p import select_eligible_peer


def _select_chat_target(warmup_session: WarmupSession, *, rng: random.Random) -> str | None:
    """Pick РѕРґРЅРѕ РїСѓР±Р»РёС‡РЅРѕРµ channel-username РёР· strategy.target_channels_json."""
    targets = warmup_session.strategy.target_channels_json or []
    candidates: list[str] = []
    for entry in targets:
        value = entry.get("username") or entry.get("chat_username") or entry.get("target")
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())
    if not candidates:
        return None
    return candidates[rng.randint(0, len(candidates) - 1)]


def _target_channel_refs(warmup_session: WarmupSession) -> list[str]:
    targets = warmup_session.strategy.target_channels_json or []
    refs: list[str] = []
    for entry in targets:
        value = entry.get("username") or entry.get("chat_username") or entry.get("target")
        if isinstance(value, str) and value.strip():
            refs.append(value.strip())
    return list(dict.fromkeys(refs))


def _subscribed_channel_states(
    session: Session, *, warmup_session: WarmupSession, channel_ref: str | None = None
) -> list[ChannelStateSnapshot]:
    refs = [channel_ref] if channel_ref is not None else _target_channel_refs(warmup_session)
    states = get_states_for_account(
        session,
        warmup_session.workspace_id,
        warmup_session.account_id,
        refs,
    )
    return [state for state in states if state.subscribed_at is not None]


def _is_channel_subscribed(
    session: Session, *, warmup_session: WarmupSession, channel_ref: str
) -> bool:
    states = get_states_for_account(
        session,
        warmup_session.workspace_id,
        warmup_session.account_id,
        [channel_ref],
    )
    return bool(states and states[0].subscribed_at is not None)


def _derive_text_seed(warmup_session: WarmupSession, action_type: str) -> str:
    raw = f"{warmup_session.id}|{warmup_session.current_day}|{action_type}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def _pause_if_blocked_by_safety_gate(
    session: Session,
    *,
    warmup_session: WarmupSession,
    now: datetime,
    worker_id: str,
) -> bool:
    from app.modules.warmup import dispatcher

    verdict = dispatcher.evaluate_safety_gate(
        session,
        workspace_id=warmup_session.workspace_id,
        account_id=warmup_session.account_id,
        intent="warmup",
    )
    if verdict.severity != "blocked":
        return False
    warmup_session.status = WarmupStatus.PAUSED_RISK.value
    warmup_session.next_micro_session_at = None
    warmup_session.next_step_at = None
    warmup_session.worker_id = worker_id
    warmup_session.updated_at = now
    write_warmup_event(
        session,
        warmup_session,
        "warmup_dispatch_blocked_by_gate",
        {"reasons": [reason.model_dump(mode="json") for reason in verdict.reasons]},
    )
    session.flush()
    return True


@dataclass(frozen=True)
class _ActionContextResolution:
    """Result of preparing per-action context before adapter invocation.

    `context` РІСЃРµРіРґР° СЃРѕРґРµСЂР¶РёС‚ Р±Р°Р·РѕРІС‹Рµ РїРѕР»СЏ (execution_mode, current_day,
    proxy_category). Р”Р»СЏ write-actions РјРѕР¶РµС‚ Р±С‹С‚СЊ РґРѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Р№
    chat_target/peer_account_id/peer_telegram_user_id/text/text_seed.

    Р•СЃР»Рё РєРѕРЅС‚РµРєСЃС‚ РЅРµРґРѕСЃС‚РёР¶РёРј (РЅР°РїСЂРёРјРµСЂ, РІ СЃС‚СЂР°С‚РµРіРёРё РЅРµС‚ channels РёР»Рё
    РІ pool РЅРµС‚ eligible peers), `skip_reason` РЅРµРїСѓСЃС‚РѕР№; `context` РІ
    СЌС‚РѕРј СЃР»СѓС‡Р°Рµ РЅРµСЂРµР»РµРІР°РЅС‚РµРЅ Рё dispatch РїРёС€РµС‚ `task_skipped`.
    """

    context: dict[str, Any]
    skip_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=lambda: {})


def _resolve_action_context(
    session: Session,
    *,
    warmup_session: WarmupSession,
    action_type: str,
    selected_channel_ref: str | None = None,
    rng: random.Random,
    text_provider: WarmupTextProvider,
    now: datetime,
) -> _ActionContextResolution:
    """РџРѕРґРіРѕС‚РѕРІРєР° РґРµС‚РµСЂРјРёРЅРёСЂРѕРІР°РЅРЅРѕРіРѕ context РґР»СЏ action.

    seed РґР»СЏ С‚РµРєСЃС‚РѕРІС‹С… Р°СЂС‚РµС„Р°РєС‚РѕРІ = sha256(session_id|day|action_type) в†’
    РѕРґРёРЅР°РєРѕРІР°СЏ СЃС‚СЂР°С‚РµРіРёСЏ + РѕРґРёРЅ РґРµРЅСЊ РґР°СЋС‚ РѕРґРёРЅ Рё С‚РѕС‚ Р¶Рµ С‚РµРєСЃС‚ РјРµР¶РґСѓ
    СЂРµСЃС‚Р°СЂС‚Р°РјРё. Р­С‚Рѕ С‚СЂРµР±РѕРІР°РЅРёРµ Phase 0a: Р°РЅС‚РёС„СЂРѕРґ-СЃРёРіРЅР°Р»С‹ РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ
    РІРѕСЃРїСЂРѕРёР·РІРѕРґРёРјС‹ РјРµР¶РґСѓ Р»РѕРіР°РјРё.
    """
    proxy_snapshot = warmup_session.proxy_snapshot_json or {}
    base: dict[str, Any] = {
        "execution_mode": warmup_session.execution_mode,
        "current_day": warmup_session.current_day,
        "proxy_category": proxy_snapshot.get("proxy_category"),
    }
    if action_type == "join_chat":
        chat_target = selected_channel_ref or _select_chat_target(warmup_session, rng=rng)
        if chat_target is None:
            return _ActionContextResolution(
                context=base, skip_reason="no_target_channels_configured"
            )
        return _ActionContextResolution(
            context={**base, "chat_target": chat_target, "channel_ref": chat_target}
        )
    if action_type == "channel_browse":
        channel_ref = selected_channel_ref or _select_chat_target(warmup_session, rng=rng)
        if channel_ref is None:
            return _ActionContextResolution(context=base, skip_reason="no_browse_target_available")
        return _ActionContextResolution(
            context={
                **base,
                "channel_ref": channel_ref,
                "history_limit": rng.randint(10, 30),
                "channel_subscribed": _is_channel_subscribed(
                    session, warmup_session=warmup_session, channel_ref=channel_ref
                ),
            }
        )
    if action_type == "view_story":
        subscribed = _subscribed_channel_states(
            session,
            warmup_session=warmup_session,
            channel_ref=selected_channel_ref,
        )
        if not subscribed:
            return _ActionContextResolution(context=base, skip_reason="not_subscribed")
        candidates = [channel for channel in subscribed if channel.has_stories is not False]
        if not candidates:
            return _ActionContextResolution(
                context=base,
                skip_reason="no_stories_in_channel",
            )
        channel = candidates[rng.randint(0, len(candidates) - 1)]
        return _ActionContextResolution(
            context={
                **base,
                "channel_ref": channel.channel_ref,
                "channel_subscribed": True,
                "has_stories": channel.has_stories,
            }
        )
    if action_type == "react_to_post":
        from app.modules.warmup import dispatcher

        verdict = dispatcher.evaluate_safety_gate(
            session,
            workspace_id=warmup_session.workspace_id,
            account_id=warmup_session.account_id,
            intent="warmup",
        )
        if verdict.severity == "blocked":
            return _ActionContextResolution(
                context=base,
                skip_reason="safety_gate_blocked",
                metadata={
                    "reasons": [reason.model_dump(mode="json") for reason in verdict.reasons]
                },
            )
        subscribed = _subscribed_channel_states(
            session,
            warmup_session=warmup_session,
            channel_ref=selected_channel_ref,
        )
        if not subscribed:
            return _ActionContextResolution(context=base, skip_reason="not_subscribed")
        candidates = [
            channel
            for channel in subscribed
            if channel.has_reactions is True and channel.available_reactions
        ]
        if not candidates:
            return _ActionContextResolution(
                context=base,
                skip_reason="no_reactions_in_channel",
            )
        channel = candidates[rng.randint(0, len(candidates) - 1)]
        return _ActionContextResolution(
            context={
                **base,
                "channel_ref": channel.channel_ref,
                "channel_subscribed": True,
                "has_reactions": True,
                "available_reactions": list(channel.available_reactions),
            }
        )
    if action_type == "p2p_send":
        peer = select_eligible_peer(
            session,
            workspace_id=warmup_session.workspace_id,
            sender_account_id=warmup_session.account_id,
            now=now,
        )
        if peer is None:
            return _ActionContextResolution(context=base, skip_reason="no_eligible_trusted_peers")
        text_seed = _derive_text_seed(warmup_session, action_type)
        if not text_provider.is_available():
            return _ActionContextResolution(
                context=base,
                skip_reason="text_provider_unavailable",
                metadata={"provider": getattr(text_provider, "provider_name", "unknown")},
            )
        rendered = text_provider.compose_p2p_message(
            TextVariationRequest(template="", seed=text_seed)
        )
        if not rendered.rendered:
            return _ActionContextResolution(
                context=base,
                skip_reason="text_provider_empty_render",
                metadata={"provider": rendered.provider},
            )
        return _ActionContextResolution(
            context={
                **base,
                "peer_account_id": peer.account_id,
                "peer_telegram_user_id": peer.telegram_user_id,
                "peer_row_id": peer.peer_row_id,
                "text": rendered.rendered,
                "text_seed": text_seed,
                "text_provider": rendered.provider,
            }
        )
    return _ActionContextResolution(context=base)
