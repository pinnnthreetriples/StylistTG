from __future__ import annotations

from fastapi import Header


def account_id_header(x_account_id: str = Header(alias="X-Account-Id")) -> str:
    return x_account_id


__all__ = ["account_id_header"]
