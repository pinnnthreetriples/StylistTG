from __future__ import annotations

import random
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.adapters.warmup_text_provider import WarmupTextProvider
from app.adapters.warmup_tdlib import WRITE_ACTION_TYPES, WarmupActionResult, WarmupTdlibAdapter
from app.models import WarmupSession

from .dispatch_context import _resolve_action_context
from .dispatch_results import _write_dispatch_skip, _write_write_action_disabled_skip


def _dispatch_action(
    session: Session,
    *,
    warmup_session: WarmupSession,
    action_type: str,
    is_live: bool,
    adapter: WarmupTdlibAdapter,
    rng: random.Random,
    text_provider: WarmupTextProvider,
    now: datetime,
) -> tuple[WarmupActionResult, dict[str, Any]] | None:
    if not is_live:
        return WarmupActionResult(
            status="ok", action_type=action_type, metadata={"simulated": True}
        ), {}
    resolution = _resolve_action_context(
        session,
        warmup_session=warmup_session,
        action_type=action_type,
        rng=rng,
        text_provider=text_provider,
        now=now,
    )
    if resolution.skip_reason is not None:
        _write_dispatch_skip(session, warmup_session, action_type, resolution)
        return None
    if action_type in WRITE_ACTION_TYPES and not adapter.supports_action(action_type):
        _write_write_action_disabled_skip(session, warmup_session, action_type)
        return None
    result = _execute_live_action(
        adapter,
        warmup_session=warmup_session,
        action_type=action_type,
        context=resolution.context,
    )
    return result, resolution.context

def _execute_live_action(
    adapter: WarmupTdlibAdapter,
    *,
    warmup_session: WarmupSession,
    action_type: str,
    context: dict[str, Any],
) -> WarmupActionResult:
    """Invoke the live adapter; convert exceptions to network_error.

    РљРѕРЅС‚СЂР°РєС‚ Р°РґР°РїС‚РµСЂР° Р·Р°РїСЂРµС‰Р°РµС‚ РёСЃРєР»СЋС‡РµРЅРёСЏ, РЅРѕ РјС‹ РґРµСЂР¶РёРј Р·Р°С‰РёС‚Сѓ, С‡С‚РѕР±С‹
    РєСЂРёРІР°СЏ СЂРµР°Р»РёР·Р°С†РёСЏ РЅРµ РІР°Р»РёР»Р° РІРѕСЂРєРµСЂ.
    """
    try:
        return adapter.execute_action(
            account_id=warmup_session.account_id,
            action_type=action_type,
            context=context,
        )
    except Exception as exc:  # defensive
        return WarmupActionResult(
            status="network_error",
            action_type=action_type,
            error_code="adapter_raised",
            error_class=exc.__class__.__name__,
            metadata={"exception_message": str(exc)[:200]},
        )
