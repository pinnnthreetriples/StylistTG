"""Compatibility wrapper.

Canonical owner: app.modules.warmup.p2p
Do not add new behavior here.
"""

from __future__ import annotations

from app.modules.warmup.p2p import (
    WarmupPeerCandidate,
    record_p2p_contact,
    select_eligible_peer,
)

__all__ = [
    "WarmupPeerCandidate",
    "record_p2p_contact",
    "select_eligible_peer",
]
