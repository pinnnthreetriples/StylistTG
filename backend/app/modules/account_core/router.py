from __future__ import annotations

from fastapi import APIRouter

from app.modules.account_core.compat_router import router as compat_router

router = APIRouter()
router.include_router(compat_router)

__all__ = ["router"]
