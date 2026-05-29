"""Compatibility wrapper.

Canonical owner: app.modules.account_core.context
Do not add new behavior here.
"""

from __future__ import annotations

from fastapi import Header

from app.modules.account_core.context import account_id_header as _account_id_header

__all__ = ["account_id_header"]


def account_id_header(x_account_id: str = Header(alias="X-Account-Id")) -> str:
    return _account_id_header(x_account_id)
