from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/neuro-commenting", tags=["neuro-commenting"])

__all__ = ["router"]
